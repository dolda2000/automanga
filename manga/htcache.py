import os, hashlib, urllib.request, time
pj = os.path.join

class cache(object):
    def __init__(self, dir):
        self.dir = dir

    def mangle(self, url):
        n = hashlib.md5()
        n.update(url.encode("ascii"))
        return n.hexdigest()

    def miss(self, url):
        with urllib.request.urlopen(url) as s:
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

home = os.getenv("HOME")
if home is None or not os.path.isdir(home):
    raise Exception("Could not find home directory for HTTP caching")
default = cache(pj(home, ".manga", "htcache"))

def fetch(url, expire=3600):
    return default.fetch(url, expire)
