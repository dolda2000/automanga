import urllib
import BeautifulSoup
import lib, htcache
soup = BeautifulSoup.BeautifulSoup

class imgstream(lib.imgstream):
    def __init__(self, url):
        self.bk = urllib.urlopen(url)
        self.ctype = self.bk.info()["Content-Type"]

    def close(self):
        self.bk.close()

    def read(self, sz = None):
        if sz is None:
            return self.bk.read()
        else:
            return self.bk.read(sz)

class page(lib.page):
    def __init__(self, chapter, n, url):
        self.chapter = chapter
        self.volume = self.chapter.volume
        self.manga = self.volume.manga
        self.n = n
        self.url = url
        self.ciurl = None

    def iurl(self):
        if self.ciurl is None:
            page = soup(htcache.fetch(self.url))
            self.ciurl = page.find("div", id="viewer").find("img", id="image")["src"]
        return self.ciurl

    def open(self):
        return imgstream(self.iurl())

class chapter(lib.pagelist):
    def __init__(self, volume, name, url):
        self.volume = volume
        self.manga = volume.manga
        self.name = name
        self.url = url
        self.cpag = None

    def __getitem__(self, i):
        return self.pages()[i]

    def __len__(self):
        return len(self.pages())

    def pages(self):
        if self.cpag is None:
            pg = soup(htcache.fetch(self.url + "1.html"))
            l = pg.find("form", id="top_bar").find("div", attrs={"class": "l"})
            if len(l.contents) != 3:
                raise Exception("parse error: weird page list for %r" % self)
            m = l.contents[2].strip()
            if m[:3] != u"of ":
                raise Exception("parse error: weird page list for %r" % self)
            self.cpag = [page(self, n + 1, self.url + ("%i.html" % (n + 1))) for n in xrange(int(m[3:]))]
        return self.cpag

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<mangafox.chapter %r.%r.%r>" % (self.manga.name, self.volume.name, self.name)

class volume(lib.pagelist):
    def __init__(self, manga, name):
        self.manga = manga
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
        if isinstance(el, BeautifulSoup.Tag):
            return el

class manga(lib.manga):
    def __init__(self, lib, name, url):
        self.lib = lib
        self.name = name
        self.url = url
        self.cvol = None

    def __getitem__(self, i):
        return self.vols()[i]

    def __len__(self):
        return len(self.vols())

    def vols(self):
        if self.cvol is None:
            page = soup(htcache.fetch(self.url))
            vls = page.find("div", id="chapters").findAll("div", attrs={"class": "slide"})
            self.cvol = []
            for i in xrange(len(vls)):
                vol = volume(self, vls[i].find("h3", attrs={"class": "volume"}).contents[0].strip())
                cls = nextel(vls[i])
                if cls.name != u"ul" or cls["class"] != u"chlist":
                    raise Exception("parse error: weird volume list for %r" % self)
                for ch in cls.findAll("li"):
                    n = ch.div.h3 or ch.div.h4
                    name = n.a.string
                    for span in ch("span"):
                        try:
                            if u" title " in (u" " + span["class"] + u" "):
                                name += " " + span.string
                        except KeyError:
                            pass
                    url = n.a["href"].encode("us-ascii")
                    if url[-7:] != "/1.html":
                        raise Exception("parse error: unexpected chapter URL for %r: %s" % (self, url))
                    vol.ch.insert(0, chapter(vol, name, url[:-6]))
                self.cvol.insert(0, vol)
        return self.cvol

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<mangafox.manga %r>" % self.name

def libalphacmp(a, b):
    return cmp(a.upper(), b.upper())

class library(lib.library):
    def __init__(self):
        self.base = "http://www.mangafox.com/"

    def alphapage(self, pno):
        page = soup(htcache.fetch(self.base + ("directory/%i.htm?az" % pno)))
        ls = page.find("div", id="mangalist").find("ul", attrs={"class": "list"}).findAll("li")
        ret = []
        for m in ls:
            t = m.find("div", attrs={"class": "manga_text"}).find("a", attrs={"class": "title"})
            name = t.string
            url = t["href"].encode("us-ascii")
            ret.append(manga(self, name, url))
        return ret

    def alphapages(self):
        page = soup(htcache.fetch(self.base + "directory/?az"))
        ls = page.find("div", id="mangalist").find("div", id="nav").find("ul").findAll("li")
        return int(ls[-2].find("a").string)

    def byname(self, prefix):
        if not isinstance(prefix, unicode):
            prefix = prefix.decode("utf8")
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

    def __iter__(self):
        raise NotImplementedError("mangafox iterator")
