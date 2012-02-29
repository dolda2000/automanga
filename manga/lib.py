class library(object):
    """Class representing a single source of multiple mangas."""
    
    def byname(self, prefix):
        """Returns an iterable object of all mangas in this library
        whose names (case-insensitively) begin with the given
        prefix.

        All libraries should implement this."""
        raise NotImplementedError()

    def __iter__(self):
        """Return an iterator of all known mangas in this library.

        Not all libraries need implement this."""
        raise NotImplementedError("manga.lib.library iterator")

class pagetree(object):
    """Base class for objects in the tree of pages and pagelists.

    All pagetree objects should contain an attribute `stack', contains
    a list of pairs. The last pair in the list should be the pagetree
    object which yielded this pagetree object, along with the index
    which yielded it. Every non-last pair should be the same
    information for the pair following it. The only objects with empty
    `stack' lists should be `manga' objects."""
    pass

class pagelist(pagetree):
    """Class representing a list of either pages, or nested
    pagelists. Might be, for instance, a volume or a chapter.

    All pagelists should contain an attribute `name', containing some
    human-readable Unicode representation of the pagelist."""

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

class manga(pagelist):
    """Class reprenting a single manga. Includes the pagelist class,
    and all constraints valid for it."""
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
    Content-Type of the image being read by the stream."""

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        """Close this stream."""
        raise NotImplementedError()

    def read(self, sz = None):
        """Read SZ bytes from the stream, or the entire rest of the
        stream of SZ is not given."""
        raise NotImplementedError()

class cursor(object):
    def __init__(self, ob):
        self.cur = self.descend(ob)

    def descend(self, ob):
        while isinstance(ob, pagelist):
            ob = ob[0]
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
        for n, i in reversed(self.cur,stack):
            if i > 0:
                self.cur = self.descend(n[i - 1])
                return self.cur
        raise StopIteration()

    def __iter__(self):
        return self
