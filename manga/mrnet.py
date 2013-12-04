import BeautifulSoup, urlparse
import lib, htcache
soup = BeautifulSoup.BeautifulSoup

class page(lib.page):
    def __init__(self, chapter, stack, n, url):
        self.stack = stack
        self.chapter = chapter
        self.manga = chapter.manga
        self.n = n
        self.id = str(n)
        self.name = u"Page %s" % n
        self.url = url
        self.ciurl = None

    def iurl(self):
        if self.ciurl is None:
            page = soup(htcache.fetch(self.url))
            self.ciurl = page.find("div", id="imgholder").find("img", id="img")["src"].encode("us-ascii")
        return self.ciurl

    def open(self):
        return lib.stdimgstream(self.iurl())

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<mrnet.page %r.%r.%r>" % (self.manga.name, self.chapter.name, self.name)

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

    def pages(self):
        if self.cpag is None:
            pg = soup(htcache.fetch(self.url))
            pag = []
            for opt in pg.find("div", id="selectpage").find("select", id="pageMenu").findAll("option"):
                url = urlparse.urljoin(self.url, opt["value"].encode("us-ascii"))
                n = int(opt.string)
                pag.append(page(self, self.stack + [(self, len(pag))], n, url))
            self.cpag = pag
        return self.cpag

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<mrnet.chapter %r.%r>" % (self.manga.name, self.name)

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

    def ch(self):
        if self.cch is None:
            page = soup(htcache.fetch(self.url))
            cls = page.find("div", id="chapterlist").find("table", id="listing")
            i = 0
            cch = []
            for tr in cls.findAll("tr"):
                td = tr.find("td")
                if td is None: continue
                cla = td.find("a")
                url = urlparse.urljoin(self.url, cla["href"].encode("us-ascii"))
                name = cla.string
                cid = name.encode("utf8")
                if isinstance(cla.nextSibling, unicode):
                    ncont = unicode(cla.nextSibling)
                    if len(ncont) > 3 and ncont[:3] == u" : ":
                        name += u": " + ncont[3:]
                cch.append(chapter(self, [(self, len(cch))], cid, name, url))
            self.cch = cch
        return self.cch

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<mrnet.manga %r>" % self.name

class library(lib.library):
    def __init__(self):
        self.base = "http://www.mangareader.net/"

    def byid(self, id):
        url = self.base + id
        page = soup(htcache.fetch(url))
        if page.find("h2", attrs={"class": "aname"}) is None:
            raise KeyError(id)
        name = page.find("h2", attrs={"class": "aname"}).string
        return manga(self, id, name, url)

    def __iter__(self):
        page = soup(htcache.fetch(self.base + "alphabetical"))
        for sec in page.findAll("div", attrs={"class": "series_alpha"}):
            for li in sec.find("ul", attrs={"class": "series_alpha"}).findAll("li"):
                url = li.a["href"].encode("us-ascii")
                name = li.a.string
                if url[:1] != "/": continue
                id = url[1:]
                if '/' in id:
                    # Does this distinction mean something?
                    id = id[id.rindex('/') + 1:]
                    if id[-5:] != ".html":
                        continue
                    id = id[:-5]
                yield manga(self, id, name, urlparse.urljoin(self.base, url))

    def byname(self, prefix):
        if not isinstance(prefix, unicode):
            prefix = prefix.decode("utf8")
        prefix = prefix.lower()
        for manga in self:
            if manga.name.lower()[:len(prefix)] == prefix:
                yield manga

    def search(self, expr):
        if not isinstance(expr, unicode):
            expr = expr.decode("utf8")
        expr = expr.lower()
        for manga in self:
            if expr in manga.name.lower():
                yield manga
