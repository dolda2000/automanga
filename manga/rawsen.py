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
        self.name = u"Page " + unicode(n)
        self.url = url
        self.ciurl = None

    def iurl(self):
        if self.ciurl is None:
            page = soup(htcache.fetch(self.url))
            for tr in page.findAll("tr"):
                img = tr.find("img", id="picture")
                if img is not None:
                    self.ciurl = urlparse.urljoin(self.url, img["src"].encode("us-ascii"))
            if self.ciurl is None:
                raise Exception("parse error: could not find image url for %r" % self)
        return self.ciurl

    def open(self):
        return lib.stdimgstream(self.iurl())

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<rawsen.page %r.%r.%r>" % (self.manga.name, self.chapter.name, self.name)

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
            if self.url[-2:] != "/1":
                raise Exception("parse error: unexpected first page url for %r" % self)
            base = self.url[:-1]
            pg = soup(htcache.fetch(self.url))
            pag = []
            for opt in pg.find("div", attrs={"class": "pager"}).find("select", attrs={"name": "page"}).findAll("option"):
                n = int(opt["value"])
                url = urlparse.urljoin(base, str(n))
                pag.append(page(self, self.stack + [(self, len(pag))], n, url))
            self.cpag = pag
        return self.cpag

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<rawsen.chapter %r.%r>" % (self.manga.name, self.name)

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
            cls = None
            for div in page.findAll("div", attrs={"class": "post"}):
                if div.h3 is not None and u"Chapter List" in div.h3.string:
                    cls = div
                    break
            if cls is None:
                raise Exception("parse error: no chapter list found for %r" % self)
            cch = []
            for tr in cls.table.findAll("tr"):
                lcol = tr.findAll("td")[1]
                if lcol.a is None: continue
                link = lcol.a
                url = link["href"].encode("us-ascii")
                name = link["title"]
                cid = name.encode("utf-8")
                cch.append(chapter(self, [(self, len(cch))], cid, name, url))
            self.cch = cch
        return self.cch

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<rawsen.manga %r>" % self.name

class library(lib.library):
    def __init__(self):
        self.base = "http://raw.senmanga.com/"

    def byid(self, id):
        url = urlparse.urljoin(self.base, id + "/")
        page = soup(htcache.fetch(url))
        name = None
        for div in page.findAll("div", attrs={"class": "post"}):
            if div.h2 is not None and div.h2.a is not None:
                curl = div.h2.a["href"].encode("us-ascii")
                if curl[-1] != '/' or curl.rfind('/', 0, -1) < 0: continue
                if curl[curl.rindex('/', 0, -1) + 1:-1] != id: continue
                name = div.h2.a.string
        if name is None:
            raise KeyError(id)
        return manga(self, id, name, url)

    def __iter__(self):
        page = soup(htcache.fetch(self.base + "Manga/"))
        for part in page.find("div", attrs={"class": "post"}).findAll("table"):
            for row in part.findAll("tr"):
                link = row.findAll("td")[1].a
                if link is None:
                    continue
                url = link["href"].encode("us-ascii")
                name = link.string
                if len(url) < 3 or url[:1] != '/' or url[-1:] != '/':
                    continue
                id = url[1:-1]
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
