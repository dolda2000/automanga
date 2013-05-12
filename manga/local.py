import os
import lib
pj = os.path.join

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

class imgstream(lib.imgstream):
    def __init__(self, path):
        self.bk = open(path, 'rb')
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
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            raise IOError("No such directory: " + path)
        self.path = path
        self.id = path
        self.stack = []
        if os.path.exists(pj(self.path, "name")):
            with open(pj(self.path, "name")) as s:
                self.name = s.readline().strip().decode("utf-8")
        else:
            self.name = os.path.basename(path).decode("utf-8")
        self.direct = self.destruct()

    def __len__(self):
        return len(self.direct)

    def __getitem__(self, idx):
        return self.direct[idx]

    def imglist(self):
        if os.path.exists(pj(self.path, "order")):
            with open(pj(self.path, "order")) as s:
                return True, [line.strip() for line in s if os.path.exists(pj(self.path, line.strip()))]
        else:
            return False, [dent for dent in os.listdir(self.path) if '.' in dent and dent[dent.rindex('.') + 1:] in self.exts]

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
        var = [i for i, part in enumerate(mx) if part == int]
        structs = [(nm, decode1(nm)) for nm in pages]
        if not ordered:
            structs.sort(key=lambda o: "".join(o[1][len(mx):]))
            for i in reversed(var):
                structs.sort(key=lambda o: int(o[1][i]))
        def constree(p, structs, idx):
            if idx == len(var):
                pages = []
                for nm, st in structs:
                    id = "".join(st[len(mx):])
                    pages.append(page(self, pj(self.path, orig[nm]), id, id, p.stack + [(p, len(pages))]))
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
                        ret.append(page(self, pj(self.path, orig[nm]), id, id, p.stack + [(p, len(ret))]))
                    else:
                        cur = interm(id, id, p.stack + [(p, len(ret))], [])
                        cur.direct = constree(cur, sub, idx + 1)
                        ret.append(cur)
                return ret
        return constree(self, structs, 0)

class dumb(lib.library):
    def byid(self, id):
        if not os.path.isdir(id):
            raise KeyError(id)
        return manga(id)

class directory(dumb):
    def __init__(self, path):
        if not os.path.isdir(path):
            raise IOError("No such directory: " + path)
        self.path = path

    def byname(self, prefix):
        ret = []
        prefix = prefix.lower()
        for dent in os.listdir(self.path):
            if dent[:len(prefix)].lower() == prefix:
                ret.append(manga(pj(self.path, dent)))
        return ret

    def __iter__(self):
        for dent in os.listdir(self.path):
            yield manga(pj(self.path, dent))

library = dumb
