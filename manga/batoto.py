import urllib.request, urllib.parse, http.cookiejar, re, bs4, os
from . import profile, lib, htcache
soup = bs4.BeautifulSoup
soupify = lambda cont: soup(cont, "html.parser")

class pageerror(Exception):
    def __init__(self, message, page):
        super().__init__(message)
        self.page = page

def byclass(el, name, cl):
    for ch in el.findAll(name):
        if not isinstance(ch, bs4.Tag): continue
        cll = ch.get("class", [])
        if cl in cll:
            return ch
    return None

def nextel(el):
    while True:
        el = el.nextSibling
        if isinstance(el, bs4.Tag):
            return el

class page(lib.page):
    def __init__(self, chapter, stack, n, url):
        self.stack = stack
        self.chapter = chapter
        self.n = n
        self.id = str(n)
        self.name = "Page %s" % n
        self.url = url
        self.ciurl = None

    def iurl(self):
        if self.ciurl is None:
            page = soupify(htcache.fetch(self.url))
            img = nextel(page.find("div", id="full_image")).img
            self.ciurl = img["src"]
        return self.ciurl

    def open(self):
        return lib.stdimgstream(self.iurl())

    def __str__(self):
        return self.name

    def __repr(self):
        return "<batoto.page %r.%r.%r>" % (self.chapter.manga.name, self.chapter.name, self.name)

class chapter(lib.pagelist):
    def __init__(self, manga, stack, id, name, url):
        self.stack = stack
        self.manga = manga
        self.id = id
        self.name = name
        self.url = url
        self.cpag = None

    def __getitem__(self, i):
        return self.pages()[i]

    def __len__(self):
        return len(self.pages())

    pnre = re.compile(r"page (\d+)")
    def pages(self):
        if self.cpag is None:
            pg = soupify(htcache.fetch(self.url))
            cpag = []
            for opt in pg.find("select", id="page_select").findAll("option"):
                url = opt["value"]
                n = int(self.pnre.match(opt.string).group(1))
                cpag.append(page(self, self.stack + [(self, len(cpag))], n, url))
            self.cpag = cpag
        return self.cpag

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<batoto.chapter %r.%r>" % (self.manga.name, self.name)

class manga(lib.manga):
    def __init__(self, lib, id, name, url):
        self.lib = lib
        self.sess = lib.sess
        self.id = id
        self.name = name
        self.url = url
        self.cch = None
        self.stack = []
        self.cnames = None

    def __getitem__(self, i):
        return self.ch()[i]

    def __len__(self):
        return len(self.ch())

    @staticmethod
    def vfylogin(page):
        if page.find("div", id="register_notice"):
            return False
        if not byclass(page, "table", "chapters_list"):
            return False
        return True

    cure = re.compile(r"/read/_/(\d+)/[^/]*")
    def ch(self):
        if self.cch is None:
            page = self.sess.lfetch(self.url, self.vfylogin)
            cls = byclass(page, "table", "chapters_list")
            if cls.tbody is not None:
                cls = cls.tbody
            scl = "lang_" + self.lib.lang
            cch = []
            for ch in cls.childGenerator():
                if isinstance(ch, bs4.Tag) and ch.name == "tr":
                    cll = ch.get("class", [])
                    if "row" in cll and scl in cll:
                        url = ch.td.a["href"]
                        m = self.cure.search(url)
                        if m is None: raise pageerror("Got weird chapter URL: %r" % url, page)
                        cid = m.group(1)
                        url = self.lib.base + "read/_/" + cid
                        name = ch.td.a.text
                        cch.append((cid, name, url))
            cch.reverse()
            rch = []
            for n, (cid, name, url) in enumerate(cch):
                rch.append(chapter(self, [(self, n)], cid, name, url))
            self.cch = rch
        return self.cch

    def altnames(self):
        if self.cnames is None:
            page = soupify(self.sess.fetch(self.url))
            cnames = None
            for tbl in page.findAll("table", attrs={"class": "ipb_table"}):
                if tbl.tbody is not None: tbl = tbl.tbody
                for tr in tbl.findAll("tr"):
                    if "Alt Names:" in tr.td.text:
                        nls = nextel(tr.td)
                        if nls.name != "td" or nls.span is None:
                            raise pageerror("Weird altnames table in " + self.id, page)
                        cnames = [nm.text.strip() for nm in nls.findAll("span")]
                        break
                if cnames is not None:
                    break
            if cnames is None:
                raise pageerror("Could not find altnames for " + self.id, page)
            self.cnames = cnames
        return self.cnames

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<batoto.manga %r>" % self.name

class credentials(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password

    @classmethod
    def fromfile(cls, path):
        username, password = None, None
        with open(path) as fp:
            for words in profile.splitlines(fp):
                if words[0] == "username":
                    username = words[1]
                elif words[0] == "password":
                    password = words[1]
                elif words[0] == "pass64":
                    import binascii
                    password = binascii.a2b_base64(words[1]).decode("utf8")
        if None in (username, password):
            raise ValueError("Incomplete profile: " + path)
        return cls(username, password)

    @classmethod
    def default(cls):
        path = os.path.join(profile.confdir, "batoto")
        if os.path.exists(path):
            return cls.fromfile(path)
        return None

class session(object):
    def __init__(self, base, credentials):
        self.base = base
        self.creds = credentials
        self.jar = http.cookiejar.CookieJar()
        self.web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.loggedin = False

    rlre = re.compile(r"Welcome, (.*) ")
    def dologin(self):
        with self.web.open(self.base) as hs:
            page = soupify(hs.read())

        cur = page.find("a", id="user_link")
        print(0)
        if cur:
            m = self.rlre.search(cur.get_text())
            if not m or m.group(1) != self.creds.username:
                print(1)
                outurl = None
                nav = page.find("div", id="user_navigation")
                if nav:
                    for li in nav.findAll("li"):
                        if li.a and "Sign Out" in li.a.string:
                            outurl = li.a["href"]
                if not outurl:
                    raise pageerror("Could not find logout URL", page)
                with self.wep.open(outurl) as hs:
                    hs.read()
                with self.web.open(self.base) as hs:
                    page = soupify(hs.read())
            else:
                print(2)
                return
        else:
            print(3)

        form = page.find("form", id="login")
        values = {}
        for el in form.findAll("input", type="hidden"):
            values[el["name"]] = el["value"]
        values["ips_username"] = self.creds.username
        values["ips_password"] = self.creds.password
        values["anonymous"] = "1"
        req = urllib.request.Request(form["action"], urllib.parse.urlencode(values).encode("ascii"))
        with self.web.open(req) as hs:
            page = soupify(hs.read())
        for resp in page.findAll("p", attrs={"class": "message"}):
            if resp.strong and "You are now signed in" in resp.strong.string:
                break
        else:
            raise pageerror("Could not log in", page)

    def login(self):
        if not self.loggedin:
            if self.creds:
                self.dologin()
            self.loggedin = True

    def open(self, url):
        return self.web.open(url)

    def fetch(self, url):
        with self.open(url) as hs:
            return hs.read()

    def lfetch(self, url, ck):
        page = soupify(self.fetch(url))
        if not ck(page):
            self.login()
            page = soupify(self.fetch(url))
            if not ck(page):
                raise pageerror("Could not verify login status despite having logged in", page)
        return page

class library(lib.library):
    def __init__(self, *, creds=None):
        if creds is None:
            creds = credentials.default()
        self.base = "http://bato.to/"
        self.sess = session(self.base, creds)
        self.lang = "English"

    def byid(self, id):
        url = self.base + "comic/_/comics/" + id
        page = soupify(self.sess.fetch(url))
        title = page.find("h1", attrs={"class": "ipsType_pagetitle"})
        if title is None:
            raise KeyError(id)
        return manga(self, id, title.string.strip(), url)

    def _search(self, pars):
        p = 1
        while True:
            _pars = dict(pars)
            _pars["p"] = str(p)
            resp = urllib.request.urlopen(self.base + "search?" + urllib.parse.urlencode(_pars).encode("ascii"))
            try:
                page = soupify(resp.read())
            finally:
                resp.close()
            rls = page.find("div", id="comic_search_results").table
            if rls.tbody is not None:
                rls = rls.tbody
            hasmore = False
            for child in rls.findAll("tr"):
                if child.th is not None: continue
                if child.get("id", "")[:11] == "comic_rowo_": continue
                if child.get("id") == "show_more_row":
                    hasmore = True
                    continue
                link = child.td.strong.a
                url = link["href"]
                m = self.rure.search(url)
                if m is None: raise Exception("Got weird manga URL: %r" % url)
                id = m.group(1)
                name = link.text.strip()
                yield manga(self, id, name, url)
            p += 1
            if not hasmore:
                break

    rure = re.compile(r"/comic/_/([^/]*)$")
    def search(self, expr):
        return self._search({"name": expr, "name_cond": "c"})

    def byname(self, prefix):
        for res in self._search({"name": prefix, "name_cond": "s"}):
            if res.name[:len(prefix)].lower() == prefix.lower():
                yield res
            else:
                for aname in res.altnames():
                    if aname[:len(prefix)].lower() == prefix.lower():
                        yield manga(self, res.id, aname, res.url)
                        break
                else:
                    if False:
                        print("eliding " + res.name)
                        print(res.altnames())
