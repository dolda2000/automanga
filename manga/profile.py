import os
pj = os.path.join

home = os.getenv("HOME")
if home is None or not os.path.isdir(home):
    raise Exception("Could not find home directory for profile keeping")
confdir = pj(home, ".manga")
basedir = pj(confdir, "profiles")

class txfile(object):
    def __init__(self, name, mode):
        self.realname = name
        self.tempname = name + ".new"
        self.bk = open(self.tempname, mode)

    def close(self, abort=False):
        self.bk.close()
        if abort:
            os.unlink(self.tempname)
        else:
            os.rename(self.tempname, self.realname)

    def read(self, sz=-1):
        return self.bk.read(sz)

    def write(self, data):
        return self.bk.write(data)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        if exc_info[0] is not None:
            self.close(True)
        else:
            self.close(False)

def openwdir(nm, mode="r"):
    ft = open
    if mode == "W":
        mode = "w"
        ft = txfile
    if os.path.exists(nm):
        return ft(nm, mode)
    if mode != "r":
        d = os.path.dirname(nm)
        if not os.path.isdir(d):
            os.makedirs(d)
    return ft(nm, mode)

def splitline(line):
    def bsq(c):
        if c == "\\": return "\\"
        elif c == '"': return '"'
        elif c == " ": return " "
        elif c == "n": return "\n"
        else: return ""
    ret = []
    p = 0
    buf = ""
    a = False
    while p < len(line):
        c = line[p]
        if c.isspace():
            p += 1
        else:
            while p < len(line):
                c = line[p]
                p += 1
                if c == '"':
                    a = True
                    while p < len(line):
                        c = line[p]
                        p += 1
                        if c == '"':
                            break
                        elif c == "\\" and p < len(line):
                            buf += bsq(line[p])
                            p += 1
                        else:
                            buf += c
                elif c.isspace():
                    ret.append(buf)
                    buf = ""
                    a = False
                    break
                elif c == "\\" and p < len(line):
                    buf += bsq(line[p])
                    p += 1
                else:
                    buf += c
    if a or buf != "":
        ret.append(buf)
    return ret

def splitlines(fp):
    for line in fp:
        cur = splitline(line)
        if len(cur) < 1:
            continue
        yield cur

def consline(*words):
    buf = ""
    for w in words:
        if any((c == "\\" or c == '"' or c == "\n" for c in w)):
            wb = ""
            for c in w:
                if c == "\\": wb += "\\\\"
                elif c == '"': wb += '\\"'
                elif c == "\n": wb += "\\n"
                else: wb += c
            w = wb
        if w == "" or any((c.isspace() for c in w)):
            w = '"' + w + '"'
        if buf != "":
            buf += " "
        buf += w
    return buf

class manga(object):
    def __init__(self, profile, libnm, id):
        self.profile = profile
        self.libnm = libnm
        self.id = id
        self.props = self.loadprops()

    def open(self):
        from . import lib
        return lib.findlib(self.libnm).byid(self.id)

    def save(self):
        pass

class memmanga(manga):
    def __init__(self, profile, libnm, id):
        super(memmanga, self).__init__(profile, libnm, id)

    def loadprops(self):
        return {}

class tagview(object):
    def __init__(self, manga):
        self.manga = manga
        self.profile = manga.profile

    def add(self, *tags):
        mt = self.getall(self.profile)
        ctags = mt.setdefault((self.manga.libnm, self.manga.id), set())
        ctags |= set(tags)
        self.save(self.profile, mt)

    def remove(self, *tags):
        mt = self.getall(self.profile)
        ctags = mt.get((self.manga.libnm, self.manga.id), set())
        ctags -= set(tags)
        if len(ctags) < 1:
            try:
                del mt[self.manga.libnm, self.manga.id]
            except KeyError:
                pass
        self.save(self.profile, mt)

    def __iter__(self):
        return iter(self.getall(self.profile).get((self.manga.libnm, self.manga.id), set()))

    @staticmethod
    def getall(profile):
        ret = {}
        try:
            with profile.file("tags") as fp:
                for words in splitlines(fp):
                    libnm, id = words[0:2]
                    tags = set(words[2:])
                    ret[libnm, id] = tags
        except IOError:
            pass
        return ret

    @staticmethod
    def save(profile, m):
        with profile.file("tags", "W") as fp:
            for (libnm, id), tags in m.items():
                fp.write(consline(libnm, id, *tags) + "\n")

    @staticmethod
    def bytag(profile, tag):
        try:
            with profile.file("tags") as fp:
                for words in splitlines(fp):
                    libnm, id = words[0:2]
                    tags = words[2:]
                    if tag in tags:
                        yield profile.getmanga(libnm, id)
        except IOError:
            pass

class filemanga(manga):
    def __init__(self, profile, libnm, id, path):
        self.path = path
        super(filemanga, self).__init__(profile, libnm, id)
        self.tags = tagview(self)

    def loadprops(self):
        ret = {}
        with openwdir(self.path) as f:
            for words in splitlines(f):
                if words[0] == "set" and len(words) > 2:
                    ret[words[1]] = words[2]
                elif words[0] == "lset" and len(words) > 1:
                    ret[words[1]] = words[2:]
        return ret

    def save(self):
        with openwdir(self.path, "W") as f:
            for key, val in self.props.items():
                if isinstance(val, str):
                    f.write(consline("set", key, val) + "\n")
                else:
                    f.write(consline("lset", key, *val) + "\n")

    def mtime(self):
        try:
            return os.stat(self.path).st_mtime
        except FileNotFoundError:
            return 0

class profile(object):
    def __init__(self, dir):
        self.dir = dir
        self.name = None

    def getmapping(self):
        seq = 0
        ret = {}
        if os.path.exists(pj(self.dir, "map")):
            with openwdir(pj(self.dir, "map")) as f:
                for words in splitlines(f):
                    if words[0] == "seq" and len(words) > 1:
                        try:
                            seq = int(words[1])
                        except ValueError:
                            pass
                    elif words[0] == "manga" and len(words) > 3:
                        try:
                            ret[words[1], words[2]] = int(words[3])
                        except ValueError:
                            pass
        return seq, ret

    def savemapping(self, seq, m):
        with openwdir(pj(self.dir, "map"), "W") as f:
            f.write(consline("seq", str(seq)) + "\n")
            for (libnm, id), num in m.items():
                f.write(consline("manga", libnm, id, str(num)) + "\n")

    def getmanga(self, libnm, id, creat=False):
        seq, m = self.getmapping()
        if (libnm, id) in m:
            return filemanga(self, libnm, id, pj(self.dir, "%i.manga" % m[(libnm, id)]))
        if not creat:
            raise KeyError("no such manga: (%s, %s)" % (libnm, id))
        while True:
            try:
                fp = openwdir(pj(self.dir, "%i.manga" % seq), "x")
            except IOError:
                seq += 1
            else:
                break
        fp.close()
        m[(libnm, id)] = seq
        self.savemapping(seq, m)
        return filemanga(self, libnm, id, pj(self.dir, "%i.manga" % seq))

    def setlast(self):
        if self.name is None:
            raise ValueError("profile at " + self.dir + " has no name")
        with openwdir(pj(basedir, "last"), "W") as f:
            f.write(self.name + "\n")

    def getaliases(self):
        ret = {}
        if os.path.exists(pj(self.dir, "alias")):
            with openwdir(pj(self.dir, "alias")) as f:
                for ln in f:
                    ln = splitline(ln)
                    if len(ln) < 1: continue
                    if ln[0] == "alias" and len(ln) > 3:
                        ret[ln[1]] = ln[2], ln[3]
        return ret

    def savealiases(self, map):
        with openwdir(pj(self.dir, "alias"), "W") as f:
            for nm, (libnm, id) in map.items():
                f.write(consline("alias", nm, libnm, id) + "\n")

    def file(self, name, mode="r"):
        return openwdir(pj(self.dir, name), mode)

    def getalias(self, nm):
        return self.getaliases()[nm]

    def setalias(self, nm, libnm, id):
        aliases = self.getaliases()
        aliases[nm] = libnm, id
        self.savealiases(aliases)

    def bytag(self, tag):
        return tagview.bytag(self, tag)

    @classmethod
    def byname(cls, name):
        if not name or name == "last" or name[0] == '.':
            raise KeyError("invalid profile name: " + name)
        ret = cls(pj(basedir, name))
        ret.name = name
        return ret

    @classmethod
    def last(cls):
        if not os.path.exists(pj(basedir, "last")):
            raise KeyError("there is no last used profile")
        with open(pj(basedir, "last")) as f:
            return cls.byname(f.readline().strip())
