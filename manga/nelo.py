import bs4, json, urllib
from urllib.parse import urljoin
from . import lib, htcache
soup = bs4.BeautifulSoup
soupify = lambda cont: soup(cont, "html.parser")

class page(lib.page):
    def __init__(self, chapter, stack, n, url):
        self.stack = stack
        self.chapter = chapter
        self.manga = chapter.manga
        self.n = n
        self.id = str(n)
        self.name = "Page %s" % (n + 1,)
        self.iurl = url

    def open(self):
        return lib.stdimgstream(self.iurl)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<nelo.page %r.%r.%r>" % (self.manga.name, self.chapter.name, self.name)

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
            pg = soupify(htcache.fetch(self.url))
            pag = []
            for n, img in enumerate(pg.find("div", attrs={"class": "container-chapter-reader"}).findAll("img")):
                url = urljoin(self.url, img["src"])
                pag.append(page(self, self.stack + [(self, n)], n, url))
            self.cpag = pag
        return self.cpag

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<nelo.chapter %r.%r>" % (self.manga.name, self.name)

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
            page = soupify(htcache.fetch(self.url))
            cls = page.find("ul", attrs={"class": "row-content-chapter"})
            cch = []
            for row in reversed(cls.findAll("li", attrs={"class": "a-h"})):
                link = row.find("a", attrs={"class": "chapter-name"})
                url = urljoin(self.url, link["href"])
                p1 = url.rfind("/")
                p2 = url.rfind("/", 0, p1 - 1)
                if p1 < 0 or p2 < 0 or url[p2 + 1 : p1] != self.id:
                    raise Exception("unexpected chapter url: %s" % (url,))
                cid = url[p1 + 1:]
                if len(cid) < 1:
                    raise Exception("unexpected chapter url: %s" % (url,))
                name = link.string
                cch.append(chapter(self, [(self, len(cch))], cid, name, url))
            self.cch = cch
        return self.cch

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<nelo.manga %r>" % self.name

class library(lib.library):
    def __init__(self):
        self.base = "https://manganelo.com/"

    def byid(self, id):
        url = urljoin(self.base + "manga/", id)
        page = soupify(htcache.fetch(url))
        div1 = page.find("div", attrs={"class": "panel-story-info"})
        if div1 is None: raise KeyError(id)
        div2 = div1.find("div", attrs={"class": "story-info-right"})
        if div2 is None: raise KeyError(id)
        name = div2.h1
        if name is None: raise KeyError(id)
        name = name.string
        return manga(self, id, name, url)

    def search(self, expr):
        values = {"searchword": expr}
        req = urllib.request.Request(self.base + "getstorysearchjson",
                                     urllib.parse.urlencode(values).encode("ascii"),
                                     headers={"User-Agent": "automanga/1"})
        with urllib.request.urlopen(req) as resp:
            rc = json.loads(resp.read().decode("utf-8"))
        for obj in rc:
            if "nameunsigned" in obj:
                try:
                    yield self.byid(obj["nameunsigned"])
                except KeyError:
                    pass
