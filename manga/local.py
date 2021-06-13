import os, pathlib
from . import lib

def decode1(nm):
    ret = []
    p = 0
    while p < len(nm):
        if nm[p].isdigit():
            s = p
            p += 1
            while p < len(nm) and nm[p].isdigit():
                p += 1
            ret += [nm[s:p]]
        elif nm[p].isalpha():
            s = p
            p += 1
            while p < len(nm) and nm[p].isalpha():
                p += 1
            ret += [nm[s:p]]
        else:
            ret += [nm[p]]
            p += 1
    return ret

def genstr(s):
    ret = []
    for part in s:
        if part.isdigit():
            ret += [int]
        else:
            ret += [part]
    return ret

def findname(names, files):
    matches = list(names.keys())
    for f in files:
        matches = [pfx for pfx in matches if f.startswith(pfx)]
        if len(matches) < 1: return None
    matches.sort(key=len, reverse=True)
    return names[matches[0]]

def prefixes(path):
    nmpath = path/"names"
    if not nmpath.exists():
        return {}
    ret = {}
    with nmpath.open("r") as fp:
        for line in fp:
            line = line.strip()
            p = line.find(' ')
            if p < 0: continue
            ret[line[:p]] = line[p + 1:]
    return ret

class imgstream(lib.imgstream):
    def __init__(self, path):
        self.bk = path.open("rb")
        self.clen = os.fstat(self.bk.fileno()).st_size

    def close(self):
        self.bk.close()

    def read(self, sz=None):
        return self.bk.read(sz)

class page(lib.page):
    def __init__(self, manga, path, name, id, stack):
        self.path = path
        self.id = id
        self.name = name
        self.manga = manga
        self.stack = stack

    def open(self):
        return imgstream(self.path)

class interm(lib.pagelist):
    def __init__(self, name, id, stack, direct):
        self.name = name
        self.id = id
        self.stack = stack
        self.direct = direct

    def __len__(self):
        return len(self.direct)

    def __getitem__(self, n):
        return self.direct[n]

def maxstruct(flist):
    mx = None
    for dent in flist:
        s = genstr(decode1(dent))
        if mx is None:
            mx = s
        else:
            nmx = []
            for p, n in zip(mx, s):
                if p == n:
                    nmx.append(p)
                else:
                    break
            mx = nmx
    return mx

class manga(lib.manga):
    exts = ["jpg", "jpeg", "png", "gif"]

    def __init__(self, path):
        path = path.resolve()
        if not path.is_dir():
            raise IOError("No such directory: " + path)
        self.path = path
        self.id = os.fspath(path)
        self.stack = []
        if (self.path/"name").exists():
            with (self.path/"name").open("r") as s:
                self.name = s.readline().strip()
        else:
            self.name = path.name
        self.direct = self.destruct()

    def __len__(self):
        return len(self.direct)

    def __getitem__(self, idx):
        return self.direct[idx]

    def imglist(self):
        if (self.path/"order").exists():
            with (self.path/"order").open("r") as s:
                return True, [line.strip() for line in s if (self.path/line.strip()).exists()]
        else:
            return False, [dent for dent in (dent.name for dent in self.path.iterdir()) if '.' in dent and dent[dent.rindex('.') + 1:] in self.exts]

    def bakenames(self, files):
        ret = []
        map = {}
        for orig in files:
            nm = orig
            if '.' in nm:
                nm = nm[:nm.rindex('.')]
            ret.append(nm)
            map[nm] = orig
        return ret, map

    def destruct(self):
        ordered, files = self.imglist()
        pages, orig = self.bakenames(files)
        mx = maxstruct(pages)
        if mx is None:
            raise TypeError("could not figure out any structure")
        var = [i for i, part in enumerate(mx) if part == int]
        structs = [(nm, decode1(nm)) for nm in pages]
        if not ordered:
            structs.sort(key=lambda o: "".join(o[1][len(mx):]))
            for i in reversed(var):
                structs.sort(key=lambda o: int(o[1][i]))
        readnames = prefixes(self.path)
        def constree(p, structs, idx):
            if idx == len(var):
                pages = []
                for nm, st in structs:
                    id = "".join(st[len(mx):])
                    pages.append(page(self, self.path/orig[nm], id, id, p.stack + [(p, len(pages))]))
                return pages
            else:
                ids = set()
                oids = []
                for nm, st in structs:
                    cur = st[var[idx]]
                    if cur not in ids:
                        ids.add(cur)
                        oids.append(cur)
                ret = []
                for id in oids:
                    sub = [(nm, st) for nm, st in structs if st[var[idx]] == id]
                    if len(sub) == 1:
                        nm, st = sub[0]
                        id = "".join(st[var[idx]:])
                        ret.append(page(self, self.path/orig[nm], id, id, p.stack + [(p, len(ret))]))
                    else:
                        name = findname(readnames, [nm for (nm, st) in sub]) or id
                        cur = interm(name, id, p.stack + [(p, len(ret))], [])
                        cur.direct = constree(cur, sub, idx + 1)
                        ret.append(cur)
                return ret
        return constree(self, structs, 0)

class dumb(lib.library):
    def byid(self, id):
        path = pathlib.Path(id)
        if not path.is_dir():
            raise KeyError(id)
        return manga(path)

class directory(dumb):
    def __init__(self, path):
        if not path.is_dir():
            raise IOError("No such directory: " + path)
        self.path = path

    def byname(self, prefix):
        ret = []
        prefix = prefix.lower()
        for dent in self.path.iterdir():
            if dent.name[:len(prefix)].lower() == prefix:
                ret.append(manga(dent))
        return ret

    def search(self, expr):
        expr = expr.lower()
        return [manga(dent) for dent in self.path.iterdir() if expr in dent.name.lower()]

    def __iter__(self):
        for dent in self.path.iterdir():
            yield manga(dent)


library = dumb
