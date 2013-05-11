import threading, gtk, gio, gobject
import lib

class notdone(Exception): pass

class future(threading.Thread):
    prog = None

    def __init__(self):
        super(future, self).__init__()
        self._val = None
        self._exc = None
        self.start()

    def run(self):
        try:
            val = self.value()
        except Exception as e:
            self._exc = e
        else:
            self._val = [val]

    @property
    def val(self):
        if self._exc is not None:
            raise self._exc
        if self._val is None:
            raise notdone()
        return self._val[0]

    @property
    def done(self):
        return self._exc != None or self._val != None

class imgload(future):
    def __init__(self, page):
        self.page = page
        self.st = None
        super(imgload, self).__init__()

    def value(self):
        buf = bytearray()
        with self.page.open() as st:
            self.p = 0
            self.st = st
            while True:
                read = st.read(1024)
                if read == "":
                    break
                self.p += len(read)
                buf.extend(read)
        self.st = None
        return gtk.gdk.pixbuf_new_from_stream(gio.memory_input_stream_new_from_data(str(buf)))

    @property
    def prog(self):
        if self.st is None or self.st.clen is None:
            return None
        return float(self.p) / float(self.st.clen)

class pageview(gtk.Widget):
    def __init__(self, pixbuf):
        super(pageview, self).__init__()
        self.pixbuf = pixbuf
        self.zoomed = None, None
        self.fit = True
        self.zoom = 1.0
        self.interp = gtk.gdk.INTERP_HYPER
        self.off = 0, 0

    def get_osize(self):
        return self.pixbuf.get_width(), self.pixbuf.get_height()

    def get_asize(self):
        return self.allocation.width, self.allocation.height

    def do_realize(self):
        self.set_flags(self.flags() | gtk.REALIZED)
        alloc = self.allocation
        self.window = gtk.gdk.Window(self.get_parent_window(),
                                     width=alloc.width, height=alloc.height,
                                     window_type = gtk.gdk.WINDOW_CHILD,
                                     wclass = gtk.gdk.INPUT_OUTPUT,
                                     event_mask = self.get_events() | gtk.gdk.EXPOSURE_MASK
                                     )
        self.window.set_user_data(self)
        self.style.attach(self.window)
        self.style.set_background(self.window, gtk.STATE_NORMAL)
        self.window.move_resize(*alloc)

    def do_unrealize(self):
        self.window.set_user_data(None)

    def do_size_request(self, req):
        req.width, req.height = self.get_osize()

    def fitzoom(self):
        w, h = self.get_osize()
        alloc = self.allocation
        return min(float(alloc.width) / float(w), float(alloc.height) / float(h))

    def do_size_allocate(self, alloc):
        self.allocation = alloc
        if self.fit:
            self.zoom = self.fitzoom()
        if self.flags() & gtk.REALIZED:
            self.window.move_resize(*alloc)

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

    def do_expose_event(self, event):
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
        gc = self.style.fg_gc[gtk.STATE_NORMAL]
        self.window.draw_pixbuf(gc, zbuf, ox, oy, dx, dy, dw, dh)

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
gobject.type_register(pageview)

class reader(gtk.Window):
    def __init__(self, manga):
        super(reader, self).__init__(gtk.WINDOW_TOPLEVEL)
        self.connect("delete_event",    lambda wdg, ev, data=None: False)
        self.connect("destroy",         lambda wdg, data=None:     self.quit())
        self.connect("key_press_event", self.key)
        self.pfr = gtk.Frame(None)
        self.pfr.set_shadow_type(gtk.SHADOW_NONE)
        self.add(self.pfr)
        self.pfr.show()

        self.manga = manga
        self.page = None
        self.cursor = lib.cursor(manga)
        self.setpage(self.cursor.cur)
        self.updtitle()

    def setpage(self, page):
        if self.page is not None:
            self.pfr.remove(self.page)
            self.page = None
        if page is not None:
            with self.cursor.cur.open() as inp:
                pb = gtk.gdk.pixbuf_new_from_stream(gio.memory_input_stream_new_from_data(inp.read()))
            self.page = pageview(pb)
            self.pfr.add(self.page)
            self.page.show()

    def updtitle(self):
        self.set_title(u"Automanga \u2013 " + self.manga.name)

    @property
    def zoom(self):
        return self.page.zoom
    @zoom.setter
    def zoom(self, zoom):
        self.page.set_zoom(zoom)

    def pan(self, off):
        ox, oy = self.page.off
        px, py = off
        self.page.set_off((ox + px, oy + py))

    def key(self, wdg, ev, data=None):
        if ev.keyval in [ord('Q'), ord('q'), 65307]:
            self.quit()
        if ev.keyval in [ord('O'), ord('o')]:
            self.zoom = 1.0
        elif ev.keyval in [ord('P'), ord('p')]:
            self.zoom = None
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
        elif ev.keyval in [ord(' ')]:
            self.setpage(self.cursor.next())
        elif ev.keyval in [65288]:
            self.setpage(self.cursor.prev())

    def quit(self):
        self.hide()
gobject.type_register(reader)
