import urllib.request, re
import bs4, json
from . import lib, htcache
soup = bs4.BeautifulSoup
soupify = lambda cont: soup(cont)

class page(lib.page):
    def __init__(self, chapter, stack, n, url):
        self.stack = stack
        self.chapter = chapter
        self.volume = self.chapter.volume
        self.manga = self.volume.manga
        self.n = n
        self.id = str(n)
        self.name = "Page %s" % n
        self.url = url
        self.ciurl = None

    def iurl(self):
        if self.ciurl is None:
            page = soupify(htcache.fetch(self.url))
            self.ciurl = page.find("div", id="viewer").find("img", id="image")["src"]
        return self.ciurl

    def open(self):
        return lib.stdimgstream(self.iurl())

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<mangafox.page %r.%r.%r.%r>" % (self.manga.name, self.volume.name, self.chapter.name, self.name)

class chapter(lib.pagelist):
    def __init__(self, volume, stack, id, name, url):
        self.stack = stack
        self.volume = volume
        self.manga = volume.manga
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
            pg = soupify(htcache.fetch(self.url + "1.html"))
            l = pg.find("form", id="top_bar").find("div", attrs={"class": "l"})
            if len(l.contents) != 3:
                raise Exception("parse error: weird page list for %r" % self)
            m = l.contents[2].strip()
            if m[:3] != "of ":
                raise Exception("parse error: weird page list for %r" % self)
            self.cpag = [page(self, self.stack + [(self, n)], n + 1, self.url + ("%i.html" % (n + 1))) for n in range(int(m[3:]))]
        return self.cpag

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<mangafox.chapter %r.%r.%r>" % (self.manga.name, self.volume.name, self.name)

class volume(lib.pagelist):
    def __init__(self, manga, stack, id, name):
        self.stack = stack
        self.manga = manga
        self.id = id
        self.name = name
        self.ch = []

    def __getitem__(self, i):
        return self.ch[i]

    def __len__(self):
        return len(self.ch)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<mangafox.volume %r.%r>" % (self.manga.name, self.name)

def nextel(el):
    while True:
        el = el.nextSibling
        if isinstance(el, bs4.Tag):
            return el

class manga(lib.manga):
    cure = re.compile(r"/c[\d.]+/$")
    
    def __init__(self, lib, id, name, url):
        self.lib = lib
        self.id = id
        self.name = name
        self.url = url
        self.cvol = None
        self.stack = []

    def __getitem__(self, i):
        return self.vols()[i]

    def __len__(self):
        return len(self.vols())

    def vols(self):
        if self.cvol is None:
            page = soupify(htcache.fetch(self.url))
            vls = page.find("div", id="chapters").findAll("div", attrs={"class": "slide"})
            cvol = []
            for i, vn in enumerate(reversed(vls)):
                name = vn.find("h3", attrs={"class": "volume"}).contents[0].strip()
                vol = volume(self, [(self, i)], name, name)
                cls = nextel(vn)
                if cls.name != "ul" or "chlist" not in cls["class"]:
                    raise Exception("parse error: weird volume list for %r" % self)
                for o, ch in enumerate(reversed(cls.findAll("li"))):
                    n = ch.div.h3 or ch.div.h4
                    name = n.a.string
                    for span in ch("span"):
                        try:
                            if "title" in span["class"]:
                                name += " " + span.string
                        except KeyError:
                            pass
                    url = n.a["href"]
                    if url[-7:] == "/1.html":
                        url = url[:-6]
                    elif self.cure.search(url) is not None:
                        pass
                    else:
                        raise Exception("parse error: unexpected chapter URL for %r: %s" % (self, url))
                    vol.ch.append(chapter(vol, vol.stack + [(vol, o)], name, name, url))
                cvol.append(vol)
            self.cvol = cvol
        return self.cvol

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<mangafox.manga %r>" % self.name

def libalphacmp(a, b):
    if a.upper() < b.upper():
        return -1
    elif a.upper() > b.upper():
        return 1
    return 0

class library(lib.library):
    def __init__(self):
        self.base = "http://mangafox.me/"

    def alphapage(self, pno):
        page = soupify(htcache.fetch(self.base + ("directory/%i.htm?az" % pno)))
        ls = page.find("div", id="mangalist").find("ul", attrs={"class": "list"}).findAll("li")
        ret = []
        ubase = self.base + "manga/"
        for m in ls:
            t = m.find("div", attrs={"class": "manga_text"}).find("a", attrs={"class": "title"})
            name = t.string
            url = t["href"]
            if url[:len(ubase)] != ubase or url.find('/', len(ubase)) != (len(url) - 1):
                raise Exception("parse error: unexpected manga URL for %r: %s" % (name, url))
            ret.append(manga(self, url[len(ubase):-1], name, url))
        return ret

    def alphapages(self):
        page = soupify(htcache.fetch(self.base + "directory/?az"))
        ls = page.find("div", id="mangalist").find("div", id="nav").find("ul").findAll("li")
        return int(ls[-2].find("a").string)

    def byname(self, prefix):
        l = 1
        r = self.alphapages()
        while True:
            if l > r:
                return
            c = l + ((r + 1 - l) // 2)
            ls = self.alphapage(c)
            if libalphacmp(ls[0].name, prefix) > 0:
                r = c - 1
            elif libalphacmp(ls[-1].name, prefix) < 0:
                l = c + 1
            else:
                pno = c
                break
        i = 0
        while i < len(ls):
            m = ls[i]
            if libalphacmp(m.name, prefix) >= 0:
                break
            i += 1
        while True:
            while i < len(ls):
                m = ls[i]
                if not m.name[:len(prefix)].upper() == prefix.upper():
                    return
                yield m
                i += 1
            pno += 1
            ls = self.alphapage(pno)
            i = 0

    def search(self, expr):
        req = urllib.request.Request(self.base + ("ajax/search.php?term=%s" % urllib.parse.quote(expr)),
                                     headers={"User-Agent": "automanga/1"})
        with urllib.request.urlopen(req) as resp:
            rc = json.loads(resp.read().decode("utf-8"))
        return [manga(self, id, name, self.base + ("manga/%s/" % id)) for num, name, id, genres, author in rc]

    def byid(self, id):
        url = self.base + ("manga/%s/" % id)
        page = soupify(htcache.fetch(url))
        if page.find("div", id="title") is None:
            # Assume we got the search page
            raise KeyError(id)
        name = page.find("div", id="series_info").find("div", attrs={"class": "cover"}).img["alt"]
        return manga(self, id, name, url)

    def __iter__(self):
        raise NotImplementedError("mangafox iterator")
