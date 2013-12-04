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

    mure = re.compile(r"/comic/_/comics/([^/]*)$")
    def search(self, expr):
        resp = urllib.urlopen(self.base + "forums/index.php?app=core&module=search&do=search&fromMainBar=1",
                              urllib.urlencode({"search_term": expr, "search_app": "ccs:database:3"}))
        try:
            page = soup(resp.read())
        finally:
            resp.close()
        ret = []
        for child in page.find("div", id="search_results").ol.childGenerator():
            if isinstance(child, BeautifulSoup.Tag) and child.name == u"li":
                info = child.find("div", attrs={"class": "result_info"})
                url = info.h3.a["href"].encode("us-ascii")
                m = self.mure.search(url)
                if m is None: raise Exception("Got weird manga URL: %r" % url)
                id = m.group(1)
                name = info.h3.a.string.strip()
                ret.append(manga(self, id, name, url))
        return ret
