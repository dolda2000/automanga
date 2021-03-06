import threading
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk, GdkPixbuf as gdkpix, Gdk as gdk, GObject as gobject
from . import lib, profile

class notdone(Exception): pass

class future(threading.Thread):
    prog = None

    def __init__(self):
        super(future, self).__init__()
        self._val = None
        self._exc = None
        self._notlist = []
        self._tstarted = False
        self.setDaemon(True)

    def start(self):
        if not self._tstarted:
            super(future, self).start()
            self._tstarted = True

    def run(self):
        try:
            val = self.value()
        except Exception as e:
            self._exc = e
            gobject.idle_add(self._callcbs, True)
        else:
            self._val = [val]
            gobject.idle_add(self._callcbs, True)

    def _callcbs(self, final):
        nls = []
        for cb in self._notlist:
            if cb():
                nls.append(cb)
        self._notlist = [] if final else nls

    # Caller must hold GDK lock
    def notify(self, cb):
        self.start()
        if not self.done:
            self._notlist.append(cb)
        else:
            cb()

    def progcb(self):
        gobject.idle_add(self._callcbs, False)

    @property
    def val(self):
        self.start()
        if self._exc is not None:
            raise self._exc
        if self._val is None:
            raise notdone()
        return self._val[0]

    @property
    def done(self):
        self.start()
        return self._exc != None or self._val != None

    def wait(self):
        self.start()
        while self.is_alive():
            self.join()
        return self.val

class imgload(future):
    def __init__(self, page):
        super(imgload, self).__init__()
        self.page = page
        self.st = None
        self.start()

    def value(self):
        buf = gdkpix.PixbufLoader()
        done = False
        try:
            with self.page.open() as st:
                self.p = 0
                self.st = st
                while True:
                    read = st.read(1024)
                    if read == b"":
                        break
                    self.p += len(read)
                    buf.write(read)
                    self.progcb()
            self.st = None
            done = True
        finally:
            try:
                buf.close()
            except:
                if done:
                    raise
        return buf.get_pixbuf()

    @property
    def prog(self):
        if self.st is None or self.st.clen is None:
            return None
        return float(self.p) / float(self.st.clen)

class pagecache(object):
    def __init__(self, sz=50):
        self.sz = sz
        self.bk = []

    def __getitem__(self, page):
        idl = page.idlist()
        for ol, f in self.bk:
            if ol == idl:
                return f
        f = imgload(page)
        self.bk.append((idl, f))
        if len(self.bk) > self.sz:
            self.bk = self.bk[-self.sz:]
        return f

    def __delitem__(self, page):
        idl = page.idlist()
        for i, (ol, f) in enumerate(self.bk):
            if ol == idl:
                del self.bk[i]
                return
        raise KeyError(idl)

class relpageget(future):
    def __init__(self, cur, prev, cache=None):
        super(relpageget, self).__init__()
        self.cur = lib.cursor(cur)
        self.prev = prev
        self.cache = cache
        self.start()

    def value(self):
        try:
            if self.prev:
                page = self.cur.prev()
            else:
                page = self.cur.next()
        except StopIteration:
            page = None
        else:
            if self.cache:
                self.cache[page]
        return page

class idpageget(future):
    def __init__(self, base, idlist):
        super(idpageget, self).__init__()
        self.bnode = base
        self.idlist = idlist

    def value(self):
        try:
            return lib.cursor(self.bnode.byidlist(self.idlist)).cur
        except KeyError:
            raise KeyError("could not find last read page: " + repr(self.idlist))

class pageget(future):
    def __init__(self, fnode):
        super(pageget, self).__init__()
        self.fnode = fnode
        self.start()

    def value(self):
        return lib.cursor(self.fnode).cur

class ccursor(object):
    def __init__(self, ob, cache=None):
        self.cur = lib.cursor(ob)
        self.prev = relpageget(self.cur, True, cache)
        self.next = relpageget(self.cur, False, cache)

class pageview(gtk.Widget):
    def __init__(self, pixbuf):
        super(pageview, self).__init__()
        self.pixbuf = pixbuf
        self.zoomed = None, None
        self.fit = True
        self.zoom = 1.0
        self.interp = gdkpix.InterpType.HYPER
        self.off = 0, 0

    def get_osize(self):
        return self.pixbuf.get_width(), self.pixbuf.get_height()

    def get_asize(self):
        alloc = self.get_allocation()
        return alloc.width, alloc.height

    def do_realize(self):
        alloc = self.get_allocation()
        attr = gdk.WindowAttr()
        attr.window_type = gdk.WindowType.CHILD
        attr.x = alloc.x
        attr.y = alloc.y
        attr.width = alloc.width
        attr.height = alloc.height
        attr.visual = self.get_visual()
        attr.event_mask = self.get_events() | gdk.EventMask.EXPOSURE_MASK
        a = gdk.WindowAttributesType
        wnd = gdk.Window(self.get_parent_window(), attr, a.X | a.Y | a.VISUAL)
        wnd.set_background_pattern(None)
        self.set_window(wnd)
        self.register_window(wnd)
        self.set_realized(True)

    # XXX: Why don't these actually get called?
    def get_preferred_width(self):
        return 0, max(min(self.get_osize()[0], 4096), 0)
    def get_preferred_height(self):
        return 0, max(min(self.get_osize()[1], 4096), 0)

    def fitzoom(self):
        w, h = self.get_osize()
        alloc = self.get_allocation()
        return min(float(alloc.width) / float(w), float(alloc.height) / float(h))

    def do_size_allocate(self, alloc):
        self.set_allocation(alloc)
        if self.fit:
            self.zoom = self.fitzoom()
        else:
            aw, ah = self.get_asize()
            zw, zh = self.get_zsize()
            ox, oy = self.off
            if zw >= aw and ox + aw > zw:
                ox = zw - aw
            if zh >= ah and oy + ah > zh:
                oy = zh - ah
            self.off = ox, oy
        if self.get_realized():
            self.get_window().move_resize(alloc.x, alloc.y, alloc.width, alloc.height)

    def get_zoomed(self):
        zoom = self.zoom
        pz, zbuf = self.zoomed
        if pz != zoom:
            w, h = self.get_osize()
            zbuf = self.pixbuf.scale_simple(int(w * zoom), int(h * zoom), self.interp)
            self.zoomed = zoom, zbuf
        return zbuf

    def get_zsize(self):
        zbuf = self.get_zoomed()
        return zbuf.get_width(), zbuf.get_height()

    def do_draw(self, cr):
        aw, ah = self.get_asize()
        dw, dh = aw, ah
        zbuf = self.get_zoomed()
        zw, zh = self.get_zsize()
        ox, oy = self.off
        dx, dy = 0, 0
        if zw < aw:
            dx = (aw - zw) / 2
            dw = zw
        if zh < ah:
            dy = (ah - zh) / 2
            dh = zh
        gdk.cairo_set_source_pixbuf(cr, zbuf, dx - ox, dy - oy)
        cr.paint()

    def set_off(self, off):
        aw, ah = self.get_asize()
        zw, zh = self.get_zsize()
        ox, oy = off
        ox, oy = int(ox), int(oy)
        if ox > zw - aw: ox = zw - aw
        if oy > zh - ah: oy = zh - ah
        if ox < 0: ox = 0
        if oy < 0: oy = 0
        self.off = ox, oy
        self.queue_draw()

    def set_zoom(self, zoom):
        if zoom is not None: zoom = float(zoom)
        aw, ah = self.get_asize()
        zw, zh = self.get_zsize()
        dw, dh = zw - aw, zh - ah
        ox, oy = self.off
        xa = float(ox) / float(dw) if dw > 0 else 0.5
        ya = float(oy) / float(dh) if dh > 0 else 0.5

        if zoom is None:
            self.fit = True
            self.zoom = self.fitzoom()
        else:
            self.fit = False
            self.zoom = zoom

        zw, zh = self.get_zsize()
        dw, dh = zw - aw, zh - ah
        ox = int(xa * dw) if dw > 0 else 0
        oy = int(ya * dh) if dh > 0 else 0
        self.set_off((ox, oy))

class msgproc(object):
    def attach(self, reader):
        self.rd = reader
        self.msg = gtk.Alignment(xalign=0.0, yalign=0.5, xscale=0.0, yscale=0.0)
        self.hlay = gtk.HBox()
        self.lbl = gtk.Label("")
        self.hlay.pack_start(self.lbl, True, True, 0)
        self.lbl.show()
        self.msg.add(self.hlay)
        self.hlay.show()
        self.rd.sbar.pack_start(self.msg, True, True, 0)
        self.msg.show()
        self._prog = None

    def prog(self, p):
        if p is not None:
            if self._prog is None:
                self._prog = gtk.ProgressBar()
                self.hlay.pack_start(self._prog, True, True, 5)
                self._prog.show()
            self._prog.set_fraction(p)
        elif p is None and self._prog is not None:
            self.hlay.remove(self._prog)
            self._prog = None

    def abort(self):
        self.rd.sbar.remove(self.msg)

class pagefetch(msgproc):
    def __init__(self, fpage, setcb=None):
        self.pg = fpage
        self.setcb = setcb

    def attach(self, reader):
        super(pagefetch, self).attach(reader)
        self.lbl.set_text("Fetching page...")
        self.pg.notify(self.haspage)

    def haspage(self):
        if self.rd.pagefetch.cur != self: return False
        if not self.pg.done:
            return True
        if self.pg.val is not None:
            self.rd.setpage(self.pg.val)
            if self.setcb is not None:
                self.setcb(self.pg.val)
        self.rd.pagefetch.set(None)

class imgfetch(msgproc):
    def __init__(self, fimage):
        self.img = fimage
        self.upd = False
        self.error = None

    def attach(self, reader):
        super(imgfetch, self).attach(reader)
        self.lbl.set_text("Fetching image...")
        self.img.notify(self.imgprog)

    def imgprog(self):
        if self.rd.imgfetch.cur != self: return False
        if self.img.done:
            try:
                img = self.img.val
            except Exception as e:
                self.error = str(e)
            else:
                self.rd.setimg(img)
                self.upd = True
            self.rd.imgfetch.set(None)
        else:
            self.prog(self.img.prog)
            return True

    def abort(self):
        self.rd.sbar.remove(self.msg)
        if not self.upd:
            self.rd.setimg(None)
            if self.error is not None:
                self.rd.pagelbl.set_text("Error fetching image: " + self.error)

class preload(msgproc):
    def __init__(self, fpage):
        self.pg = fpage

    def attach(self, reader):
        super(preload, self).attach(reader)
        self.lbl.set_text("Fetching next page...")
        self.pg.notify(self.haspage)

    def haspage(self):
        if self.rd.preload.cur != self: return False
        if not self.pg.done: return True
        if self.pg.val is not None:
            self.img = self.rd.cache[self.pg.val]
            self.lbl.set_text("Loading next page...")
            self.img.notify(self.imgprog)
        else:
            self.rd.preload.set(None)

    def imgprog(self):
        if self.rd.preload.cur != self: return False
        if self.img.done:
            self.rd.preload.set(None)
        else:
            self.prog(self.img.prog)
            return True

    def abort(self):
        self.rd.sbar.remove(self.msg)

class procslot(object):
    __slots__ = ["cur", "p"]
    def __init__(self, p):
        self.cur = None
        self.p = p

    def set(self, proc):
        if self.cur is not None:
            self.cur.abort()
            self.cur = None
        if proc is not None:
            self.cur = proc
            try:
                proc.attach(self.p)
            except:
                self.cur = None
                raise

class plistget(future):
    def __init__(self, node):
        super(plistget, self).__init__()
        self.node = node

    def value(self):
        return list(self.node)

class loadplist(object):
    def __init__(self, pnode):
        self.pnode = pnode
        self.flist = plistget(self.pnode)

    def attach(self, sbox):
        self.sbox = sbox
        self.flist.notify(self.haslist)

    def haslist(self):
        if self.sbox.loadlist.cur != self: return False
        if not self.flist.done: return True
        self.sbox.setlist(self.flist.val)

class sbox(gtk.ComboBox):
    def __init__(self, reader, ptnode):
        super(sbox, self).__init__()
        self.rd = reader
        self.node = ptnode
        self.pnode, self.pidx = self.node.stack[-1]

        self.bk = gtk.ListStore(str)
        self.set_model(self.bk)
        cell = gtk.CellRendererText()
        self.pack_start(cell, True)
        self.add_attribute(cell, "text", 0)
        self.set_active(0)

        self.set_sensitive(False)
        self.set_focus_on_click(False)
        self.bk.append([ptnode.name])
        self.loadlist = procslot(self)
        self.loadlist.set(loadplist(self.pnode))

    def setlist(self, ls):
        self.bk.clear()
        for i, ch in enumerate(ls):
            self.bk.append(["%i/%i: %s" % (i + 1, len(ls), ch.name)])
        self.set_active(self.pidx)
        self.set_sensitive(True)
        self.connect("changed", self.changed_cb)

    def changed_cb(self, wdg, data=None):
        self.rd.fetchpage(pageget(self.pnode[self.get_active()]))

class profprop(object):
    def __init__(self, key, default=None):
        self.key = key
        self.default = default

    def __get__(self, ins, cls):
        return ins.profile.props.get(self.key, self.default)

    def __set__(self, ins, val):
        ins.profile.props[self.key] = val
        ins.profile.save()

    def __delete__(self, ins):
        del ins.profile.props[self.key]
        ins.profile.save()

class reader(gtk.Window):
    def __init__(self, manga, prof=None):
        super(reader, self).__init__()
        self.connect("delete_event",    lambda wdg, ev, data=None: False)
        self.connect("destroy",         lambda wdg, data=None:     self.quit())
        self.connect("key_press_event", self.key)
        self.cache = pagecache()
        self.pagefetch = procslot(self)
        self.imgfetch = procslot(self)
        self.preload = procslot(self)
        self.profile = prof if prof else profile.memmanga(None, None, manga.id)

        self.manga = manga
        self.page = None
        self.sboxes = []
        self.point = None

        vlay = gtk.VBox()
        self.pfr = gtk.Frame()
        self.pfr.set_shadow_type(gtk.ShadowType.NONE)
        vlay.pack_start(self.pfr, True, True, 0)
        self.pfr.show()
        self.sboxbar = gtk.HBox()
        algn = gtk.Alignment(xalign=0.0, yalign=0.5, xscale=0.0, yscale=0.0)
        sboxlbl = gtk.Label(self.manga.name + ": ")
        algn.add(sboxlbl)
        sboxlbl.show()
        self.sboxbar.pack_start(algn, False, True, 0)
        algn.show()
        vlay.pack_start(self.sboxbar, False, True, 0)
        self.sboxbar.show()
        self.sbar = gtk.HBox()
        self.pagelbl = gtk.Label("")
        algn = gtk.Alignment(xalign=0.0, yalign=0.5, xscale=0.0, yscale=0.0)
        algn.add(self.pagelbl)
        self.pagelbl.show()
        self.sbar.pack_start(algn, True, True, 0)
        algn.show()
        vlay.pack_end(self.sbar, False, True, 0)
        self.sbar.show()
        self.add(vlay)
        vlay.show()

        if self.curpage is not None:
            self.fetchpage(idpageget(self.manga, self.curpage))
        else:
            self.fetchpage(pageget(self.manga))
        self.updtitle()

    zmode = profprop("zmode", "fit")
    curpage = profprop("curpage")

    def updpagelbl(self):
        if self.page is None:
            self.pagelbl.set_text("")
        else:
            w, h = self.page.get_osize()
            self.pagelbl.set_text("%s\u00d7%s (%d%%)" % (w, h, int(self.page.zoom * 100)))

    def updsboxes(self, page):
        nodes = [node for node, idx in page.stack[1:]] + [page]
        l = min(len(self.sboxes), len(nodes))
        for i, (pbox, node) in enumerate(zip(self.sboxes, nodes)):
            if pbox.node != node:
                l = i
                break
        for i in range(l, len(self.sboxes)):
            self.sboxbar.remove(self.sboxes[i])
        self.sboxes = self.sboxes[:l]
        for i in range(l, len(nodes)):
            new = sbox(self, nodes[i])
            self.sboxbar.pack_start(new, False, True, 5)
            self.sboxes.append(new)
            new.show()

    def setimg(self, img):
        if self.page is not None:
            self.pfr.remove(self.page)
            self.page = None
        if img is not None:
            self.page = pageview(img)
            if self.zmode == "1":
                self.page.set_zoom(1)
                self.page.set_off((0, 0))
            self.pfr.add(self.page)
            self.page.show()
        self.updpagelbl()

    def setpage(self, page):
        if self.point is not None:
            self.point = None
        if page is not None:
            self.curpage = page.idlist()
            self.point = ccursor(page, self.cache)
            self.imgfetch.set(imgfetch(self.cache[page]))
        else:
            self.setimg(None)
        self.updsboxes(page)

    def fetchpage(self, fpage, setcb=None):
        self.imgfetch.set(None)
        proc = pagefetch(fpage, setcb)
        self.pagefetch.set(proc)
        return proc

    def updtitle(self):
        self.set_title("Automanga \u2013 " + self.manga.name)

    @property
    def zoom(self):
        return self.page.zoom
    @zoom.setter
    def zoom(self, zoom):
        self.page.set_zoom(zoom)
        self.updpagelbl()

    def pan(self, off):
        ox, oy = self.page.off
        px, py = off
        self.page.set_off((ox + px, oy + py))

    def key(self, wdg, ev, data=None):
        if ev.keyval in [ord('Q'), ord('q')]:
            self.quit()
        elif ev.keyval in [65307]:
            if self.page is not None:
                self.pagefetch.set(None)
            self.imgfetch.set(None)
        if self.page is not None:
            if ev.keyval in [ord('O'), ord('o')]:
                self.zoom = 1.0
                self.zmode = "1"
            elif ev.keyval in [ord('P'), ord('p')]:
                self.zoom = None
                self.zmode = "fit"
            elif ev.keyval in [ord('[')]:
                self.zoom = min(self.zoom * 1.25, 3)
            elif ev.keyval in [ord(']')]:
                self.zoom /= 1.25
            elif ev.keyval in [ord('h')]:
                self.pan((-100, 0))
            elif ev.keyval in [ord('j')]:
                self.pan((0, 100))
            elif ev.keyval in [ord('k')]:
                self.pan((0, -100))
            elif ev.keyval in [ord('l')]:
                self.pan((100, 0))
            elif ev.keyval in [ord('H')]:
                self.page.set_off((0, self.page.off[1]))
            elif ev.keyval in [ord('J')]:
                self.page.set_off((self.page.off[0], self.page.get_asize()[1]))
            elif ev.keyval in [ord('K')]:
                self.page.set_off((self.page.off[1], 0))
            elif ev.keyval in [ord('L')]:
                self.page.set_off((self.page.get_asize()[0], self.page.off[1]))
        if self.point is not None:
            if ev.keyval in [ord(' ')]:
                if self.page and self.page.off[1] + self.page.get_asize()[1] < self.page.get_zsize()[1]:
                    self.pan((0, self.page.get_asize()[1] - 50))
                else:
                    self.fetchpage(self.point.next, lambda page: self.preload.set(preload(relpageget(page, False, self.cache))))
            elif ev.keyval in [65288]:
                if self.page and self.page.off[1] > 0:
                    self.pan((0, -(self.page.get_asize()[1] - 50)))
                else:
                    self.fetchpage(self.point.prev, lambda page: self.preload.set(preload(relpageget(page, True, self.cache))))
            elif ev.keyval in [ord('R'), ord('r')]:
                page = self.point.cur.cur
                del self.cache[page]
                self.imgfetch.set(imgfetch(self.cache[page]))

    def quit(self):
        self.hide()
        gtk.main_quit()
gobject.type_register(reader)
