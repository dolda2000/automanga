import urllib, re, BeautifulSoup
import lib, htcache
soup = BeautifulSoup.BeautifulSoup

def byclass(el, name, cl):
    for ch in el.findAll(name):
        if not isinstance(ch, BeautifulSoup.Tag): continue
        cll = ch.get("class", "")
        if cl in cll.split():
            return ch
    return None

def nextel(el):
    while True:
        el = el.nextSibling
        if isinstance(el, BeautifulSoup.Tag):
            return el

class page(lib.page):
    def __init__(self, chapter, stack, n, url):
        self.stack = stack
        self.chapter = chapter
        self.n = n
        self.id = str(n)
        self.name = u"Page %s" % n
        self.url = url
        self.ciurl = None

    def iurl(self):
        if self.ciurl is None:
            page = soup(htcache.fetch(self.url))
            img = nextel(page.find("div", id="full_image")).img
            self.ciurl = img["src"].encode("us-ascii")
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
            pg = soup(htcache.fetch(self.url))
            cpag = []
            for opt in pg.find("select", id="page_select").findAll("option"):
                url = opt["value"].encode("us-ascii")
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

    cure = re.compile(r"/read/_/(\d+)/[^/]*")
    def ch(self):
        if self.cch is None:
            page = soup(htcache.fetch(self.url))
            cls = byclass(page, u"table", u"chapters_list")
            if cls.tbody is not None:
                cls = cls.tbody
            scl = u"lang_" + self.lib.lang
            cch = []
            for ch in cls.childGenerator():
                if isinstance(ch, BeautifulSoup.Tag) and ch.name == u"tr":
                    cll = ch.get("class", "").split()
                    if u"row" in cll and scl in cll:
                        url = ch.td.a["href"].encode("us-ascii")
                        m = self.cure.search(url)
                        if m is None: raise Exception("Got weird chapter URL: %r" % url)
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
            page = soup(htcache.fetch(self.url))
            cnames = None
            for tbl in page.findAll("table", attrs={"class": "ipb_table"}):
                if tbl.tbody is not None: tbl = tbl.tbody
                for tr in tbl.findAll("tr"):
                    if u"Alt Names:" in tr.td.text:
                        nls = nextel(tr.td)
                        if nls.name != u"td" or nls.span is None:
                            raise Exception("Weird altnames table in " + self.id)
                        cnames = [nm.text.strip() for nm in nls.findAll("span")]
                        break
                if cnames is not None:
                    break
            if cnames is None:
                raise Exception("Could not find altnames for " + self.id)
            self.cnames = cnames
        return self.cnames

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<batoto.manga %r>" % self.name

class library(lib.library):
    def __init__(self):
        self.base = "http://www.batoto.net/"
        self.lang = u"English"

    def byid(self, id):
        url = self.base + "comic/_/comics/" + id
        page = soup(htcache.fetch(url))
        title = page.find("h1", attrs={"class": "ipsType_pagetitle"})
        if title is None:
            raise KeyError(id)
        return manga(self, id, title.string.strip(), url)

    def _search(self, pars):
        p = 1
        while True:
            _pars = dict(pars)
            _pars["p"] = str(p)
            resp = urllib.urlopen(self.base + "search?" + urllib.urlencode(_pars))
            try:
                page = soup(resp.read())
            finally:
                resp.close()
            rls = page.find("div", id="comic_search_results").table
            if rls.tbody is not None:
                rls = rls.tbody
            hasmore = False
            for child in rls.findAll("tr"):
                if child.th is not None: continue
                if child.get("id", u"")[:11] == u"comic_rowo_": continue
                if child.get("id") == u"show_more_row":
                    hasmore = True
                    continue
                link = child.td.strong.a
                url = link["href"].encode("us-ascii")
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
        if not isinstance(expr, unicode):
            expr = expr.decode("utf8")
        return self._search({"name": expr.encode("utf8"), "name_cond": "c"})

    def byname(self, prefix):
        if not isinstance(prefix, unicode):
            prefix = prefix.decode("utf8")
        for res in self._search({"name": prefix.encode("utf8"), "name_cond": "s"}):
            if res.name[:len(prefix)].lower() == prefix.lower():
                yield res
            else:
                for aname in res.altnames():
                    if aname[:len(prefix)].lower() == prefix.lower():
                        yield manga(self, res.id, aname, res.url)
                        break
                else:
                    if False:
                        print "eliding " + res.name
                        print res.altnames()