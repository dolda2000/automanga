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

class pagelist(object):
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

class page(object):
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

class pageiter(object):
    def __init__(self, root):
        self.nstack = [0]
        self.lstack = [root]

    def next(self):
        while True:
            if len(self.nstack) == 0:
                raise StopIteration
            try:
                node = self.lstack[-1][self.nstack[-1]]
            except IndexError:
                self.lstack.pop()
                self.nstack.pop()
                if len(self.nstack) > 0:
                    self.nstack[-1] += 1
                continue
            if isinstance(node, page):
                nl = tuple(self.nstack)
                self.nstack[-1] += 1
                return nl, node
            elif isinstance(node, pagelist):
                self.lstack.append(node)
                self.nstack.append(0)

    def __iter__(self):
        return self
