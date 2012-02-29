class library(object):
    pass

class pagelist(object):
    pass

class manga(pagelist):
    pass

class page(object):
    pass

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
