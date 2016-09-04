import os, hashlib, urllib.request, time
from . import profile
pj = os.path.join

class notfound(Exception):
    pass

class cache(object):
    def __init__(self, dir):
        self.dir = dir

    def mangle(self, url):
        n = hashlib.md5()
        n.update(url.encode("ascii"))
        return n.hexdigest()

    def open(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "automanga/1"})
        return urllib.request.urlopen(req)

    def miss(self, url):
        try:
            s = self.open(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise notfound(url)
            raise
        with s:
            if s.headers.get("content-encoding") == "gzip":
                import gzip, io
                return gzip.GzipFile(fileobj=io.BytesIO(s.read()), mode="r").read()
            return s.read()

    def fetch(self, url, expire=3600):
        path = pj(self.dir, self.mangle(url))
        if os.path.exists(path):
            if time.time() - os.stat(path).st_mtime < expire:
                with open(path, "rb") as f:
                    return f.read()
        data = self.miss(url)
        if not os.path.isdir(self.dir):
            os.makedirs(self.dir)
        with open(path, "wb") as f:
            f.write(data)
        return data

default = cache(pj(profile.confdir, "htcache"))

def fetch(url, expire=3600):
    return default.fetch(url, expire)
