class library(object):
    """Class representing a single source of multiple mangas."""
    
    def byname(self, prefix):
        """Returns an iterable object of all mangas in this library
        whose names (case-insensitively) begin with the given
        prefix.

        All libraries should implement this."""
        raise NotImplementedError()

    def search(self, string):
        """Returns an iterable object of mangas in this library that
        matches the search string in a library-dependent manner. While
        each library is at liberty to define its own matching
        criteria, it is probably likely to involve something akin to
        searching for keywords in the titles of the library.

        Searching may return very many results and may be slow to
        iterate.

        Not all libraries need implement this."""
        raise NotImplementedError()

    def byid(self, id):
        """Returns a previously known manga by its string ID, or
        raises KeyError if no such manga could be found.

        All libraries should implement this."""
        raise KeyError(id)

    def __iter__(self):
        """Return an iterator of all known mangas in this library.

        Not all libraries need implement this."""
        raise NotImplementedError("manga.lib.library iterator")

class pagetree(object):
    """Base class for objects in the tree of pages and pagelists.

    All pagetree objects should contain an attribute `stack',
    containing a list of pairs. The last pair in the list should be
    the pagetree object which yielded this pagetree object, along with
    the index which yielded it. Every non-last pair should be the same
    information for the pair following it. The only objects with empty
    `stack' lists should be `manga' objects.
    
    All non-root pagetree objects should also contain an attribute
    `id', which should be a string that can be passed to the `byid'
    function of its parent node to recover the node. Such string ID
    should be more persistent than the node's numeric index in the
    parent.

    All pagetree objects should contain an attribute `name',
    containing some human-readable Unicode representation of the
    pagelist."""
    
    def idlist(self):
        """Returns a list of the IDs necessary to resolve this node
        from the root node."""
        if len(self.stack) == 0:
            return []
        return self.stack[-1][0].idlist() + [self.id]

    def byidlist(self, idlist):
        if len(idlist) == 0:
            return self
        return self.byid(idlist[0]).byidlist(idlist[1:])

class pagelist(pagetree):
    """Class representing a list of either pages, or nested
    pagelists. Might be, for instance, a volume or a chapter."""

    def __len__(self):
        """Return the number of (direct) sub-nodes in this pagelist.

        All pagelists need to implement this."""
        raise NotImplementedError()

    def __getitem__(self, idx):
        """Return the direct sub-node of the given index in this
        pagelist. Sub-node indexes are always zero-based and
        contiguous, regardless of any gaps in the underlying medium,
        which should be indicated instead by way of the `name'
        attribute.

        All pagelists need to implement this."""
        raise NotImplementedError()

    def byid(self, id):
        """Return the direct sub-node of this pagelist which has the
        given string ID. If none is found, a KeyError is raised.

        This default method iterates the children of this node, but
        may be overridden by some more efficient implementation.
        """
        for ch in self:
            if ch.id == id:
                return ch
        raise KeyError(id)

class manga(pagelist):
    """Class reprenting a single manga. Includes the pagelist class,
    and all constraints valid for it.

    A manga is a root pagetree node, but should also contain an `id'
    attribute, which can be used to recover the manga from its
    library's `byid' function."""
    pass

class page(pagetree):
    """Class representing a single page of a manga. Pages make up the
    leaf nodes of a pagelist tree.

    All pages should contain an attribute `manga', referring back to
    the containing manga instance."""
    
    def open(self):
        """Open a stream for the image this page represents. The
        returned object should be an imgstream class.

        All pages need to implement this."""
        raise NotImplementedError()

class imgstream(object):
    """An open image I/O stream for a manga page. Generally, it should
    be file-like. This base class implements the resource-manager
    interface for use in `with' statements, calling close() on itself
    when exiting the with-scope.

    All imgstreams should contain an attribute `ctype', being the
    Content-Type of the image being read by the stream, and `clen`,
    being either an int describing the total number of bytes in the
    stream, or None if the value is not known in advance."""

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def fileno(self):
        """If reading the imgstream may block, fileno() should return
        a file descriptor that can be polled. If fileno() returns
        None, that should mean that reading will not block."""
        return None

    def close(self):
        """Close this stream."""
        raise NotImplementedError()

    def read(self, sz=None):
        """Read SZ bytes from the stream, or the entire rest of the
        stream of SZ is not given."""
        raise NotImplementedError()

class stdimgstream(imgstream):
    """A standard implementation of imgstream, for libraries which
    have no particular implementation requirements."""

    def __init__(self, url):
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "automanga/1"})
        print(req)
        self.bk = urllib.request.urlopen(req)
        ok = False
        try:
            if self.bk.getcode() != 200:
                raise IOError("Server error: " + str(self.bk.getcode()))
            self.ctype = self.bk.info()["Content-Type"]
            self.clen = int(self.bk.info()["Content-Length"])
            ok = True
        finally:
            if not ok:
                self.bk.close()

    def fileno(self):
        return self.bk.fileno()

    def close(self):
        self.bk.close()

    def read(self, sz=None):
        if sz is None:
            return self.bk.read()
        else:
            return self.bk.read(sz)

class cursor(object):
    def __init__(self, ob):
        if isinstance(ob, cursor):
            self.cur = ob.cur
        else:
            self.cur = self.descend(ob)

    def descend(self, ob, last=False):
        while isinstance(ob, pagelist):
            ob = ob[len(ob) - 1 if last else 0]
        if not isinstance(ob, page):
            raise TypeError("object in page tree was unexpectedly not a pagetree")
        return ob

    def next(self):
        for n, i in reversed(self.cur.stack):
            if i < len(n) - 1:
                self.cur = self.descend(n[i + 1])
                return self.cur
        raise StopIteration()

    def prev(self):
        for n, i in reversed(self.cur.stack):
            if i > 0:
                self.cur = self.descend(n[i - 1], True)
                return self.cur
        raise StopIteration()

    def __iter__(self):
        return self

loaded = {}
def findlib(name):
    def load(name):
        import importlib
        mod = importlib.import_module(name)
        if not hasattr(mod, "library"):
            raise ImportError("module " + name + " is not a manga library")
        return mod.library()
    if name not in loaded:
        try:
            loaded[name] = load("manga." + name)
        except ImportError:
            loaded[name] = load(name)
    return loaded[name]
