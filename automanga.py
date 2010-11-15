#!/usr/bin/python
#encoding: utf8
#
# automanga
# by Kaka <kaka@dolda2000.com>

import os, sys, optparse
from user import home
try:
    import gtk
    import pygtk; pygtk.require("2.0")
except AssertionError, e:
    error("You need to install the package 'python-gtk2'")

DIR_BASE      = os.path.join(home, ".automanga")
DIR_PROFILES  = os.path.join(DIR_BASE, "profiles")
FILE_SETTINGS = os.path.join(DIR_BASE, "settings")

def init():
    global settings, profile, opts, args, cwd

    if not os.path.exists(DIR_PROFILES):
        os.makedirs(DIR_PROFILES)
    settings = Settings()

    usage = "Usage: %prog [options]"
    parser = optparse.OptionParser(usage) # one delete option to use in combination with profile and directory?
    parser.add_option("-p", "--profile", help="load or create a profile", metavar="profile")
    parser.add_option("-r", "--remove-profile", help="remove profile",    metavar="profile")
    parser.add_option("-a", "--add",     help="add a directory",          metavar="dir")
    parser.add_option("-d", "--delete",  help="delete a directory",       metavar="dir")
    parser.add_option("-s", "--silent",  help="no output",                default=False, action="store_true")
    parser.add_option("-v", "--verbose", help="show output",              default=False, action="store_true")
    opts, args = parser.parse_args()

    cwd = os.getcwd()

def load_profile(name):
    global profile
    profile = Profile(name)
    settings.last_profile(profile.name)

def output(msg):
    if not settings.silent():
        print msg

def error(msg):
    print >>sys.stderr, msg
    sys.exit(1)

def abs_path(path):
    """Returns the absolute path"""
    if not os.path.isabs(path): ret = os.path.join(cwd, path)
    else:                       ret = path
    return os.path.abspath(ret)

def manga_dir(path):
    """Checks if path is a manga directory"""
    for node in os.listdir(path):
        if node.rsplit(".", 1)[-1] in ("jpg", "png", "gif", "bmp"):
            return True
    return False

def natsorted(strings):
    """Sorts a list of strings naturally"""
#    import re
#    return sorted(strings, key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)])
    return sorted(strings, key=lambda s: [int(t) if t.isdigit() else t for t in s.rsplit(".")[0].split("-")])

class Reader(object):
    """GUI"""
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event",    lambda widget, event, data = None: False)
        self.window.connect("destroy",         lambda widget, data = None: self.quit())
        self.window.connect("key_press_event", self.keypress)
#        self.window.set_border_width(10)
        self.window.set_position(gtk.WIN_POS_CENTER) # save position in settings?
#        self.window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#222")) # seems to do nothing

        self.set_title()
        self.fullscreen = False
        self.cursor     = None

        self.container = gtk.VBox()
        self.menu_bar = self.build_menu()
        self.page_bar = gtk.HBox()
        self.key = gtk.Label()
#        self.key.set_padding(10, 10)
        self.page_num = gtk.Label()
        self.page = gtk.Image()
        self.sep = gtk.HSeparator()
        self.sbar = gtk.Statusbar(); self.sbar.show(); self.sbar.set_has_resize_grip(False)

        self.combo = gtk.combo_box_new_text()
        self.combo.set_wrap_width(2)
        for i in range(50):
            self.combo.append_text('item - %d' % i)
        self.combo.set_active(0)

        self.page_bar.pack_start(self.key, expand=False)
        vsep = gtk.VSeparator(); vsep.show(); self.page_bar.pack_start(vsep, expand=False)
#        self.page_bar.pack_start(self.combo, expand=False); self.combo.show()
        self.page_bar.pack_start(self.page_num, expand=False)
#        self.container.pack_start(self.menu_bar, expand=False)
        self.container.pack_start(self.page_bar, expand=False)
        self.container.pack_start(self.sep, expand=False)
        self.container.pack_start(self.page)
        self.container.pack_start(self.sbar, expand=False)
        self.window.add(self.container)

        self.key.show()
        self.page_num.show()
        self.sep.show()
        self.page.show()
        self.page_bar.show()
        self.container.show()
        self.window.show()

    def build_menu(self):
        menus = (("_File", (
                    ("_New profile",    gtk.STOCK_NEW,         lambda widget, data: None),
                    ("_Load profile",   gtk.STOCK_OPEN,        lambda widget, data: None),
                    ("_Delete profile", gtk.STOCK_DELETE,      lambda widget, data: None),
                    (),
                    ("_Quit",           gtk.STOCK_QUIT,        lambda widget, data: self.quit()),
                    )),
                 ("_Edit", (
                    ("_Profile",        gtk.STOCK_EDIT,        lambda widget, data: None),
                    (),
                    ("_Settings",       gtk.STOCK_PREFERENCES, lambda widget, data: None),
                    )),
                 )
        menu_bar = gtk.MenuBar()
        menu_bar.show()
        for submenu in menus:
            lbl, items = submenu
            menu = gtk.Menu()
            menu.show()
            mi = gtk.MenuItem(lbl, True)
            mi.show()
            mi.set_submenu(menu)
            menu_bar.add(mi)
            for item in items:
                if not item:
                    mi = gtk.SeparatorMenuItem()
                    mi.show()
                    menu.add(mi)
                else:
                    lbl, icon, func = item
                    img = gtk.Image()
                    img.set_from_stock(icon, gtk.ICON_SIZE_MENU)
                    mi = gtk.ImageMenuItem(lbl, True)
                    mi.show()
                    mi.set_image(img)
                    mi.connect("activate", func, None)
                    menu.add(mi)
        return menu_bar

    def start(self):
        gtk.main()

    def quit(self):
        gtk.main_quit()

    def set_title(self, title = None):
        self.window.set_title("Automanga" + (" - " + title if title else ""))

    def set_manga(self, manga):
        self.manga = manga
        self.set_title(manga.title())
        self.cursor = manga.mark
        self.update_page()

    def update_page(self):
        self.page.set_from_file(self.cursor.path)
        self.page_num.set_label("Mark's at %s (%s/%s)\t\tYou're at %s (%s/%s)" % (self.manga.mark.name, self.manga.index_of(self.manga.mark) + 1, self.manga.num_pages(), self.cursor.name, self.manga.index_of(self.cursor) + 1, self.manga.num_pages()))
        self.window.resize(*self.container.size_request())

        self.sbar.pop(self.sbar.get_context_id("stat"))
        self.sbar.push(self.sbar.get_context_id("stat"), "Mark's at %s (%s/%s)\t\tYou're at %s (%s/%s)" % (self.manga.mark.name, self.manga.index_of(self.manga.mark) + 1, self.manga.num_pages(), self.cursor.name, self.manga.index_of(self.cursor) + 1, self.manga.num_pages()))

    def keypress(self, widget, event, data = None):
        if   event.keyval in [32]:             self.read_page(1)        # space
        elif event.keyval in [65288]:          self.read_page(-1)       # backspace
        elif event.keyval in [65362, 65363]:   self.browse_page(1)      # up, right
        elif event.keyval in [65361, 65364]:   self.browse_page(-1)     # left, down
        elif event.keyval in [70, 102]:        self.toggle_fullscreen() # f, F
        elif event.keyval in [81, 113, 65307]: self.quit()              # q, Q, esc
        elif event.keyval in [65360]:          self.browse_start()      # home
        elif event.keyval in [65367]:          self.browse_end()        # end
        else: self.key.set_text(str(event.keyval))

    def browse_page(self, step):
        self.cursor = self.cursor.previous() if step < 0 else self.cursor.next()
        self.update_page()

    def read_page(self, step):
        if self.cursor == self.manga.mark:
            if step < 0: self.manga.set_mark(self.cursor.previous())
            else:        self.cursor = self.cursor.next()
        if step < 0: self.cursor = self.manga.mark
        else:        self.manga.set_mark(self.cursor)
        self.update_page()

    def browse_start(self):
        self.cursor = self.manga.first_page()
        self.update_page()

    def browse_end(self):
        self.cursor = self.manga.last_page()
        self.update_page()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
#         if self.fullscreen: self.window.fullscreen()
#         else:               self.window.unfullscreen()
        if self.fullscreen:
            self.window.set_decorated(False)
            self.window.set_position(gtk.WIN_POS_CENTER_ALWAYS)
            self.menu_bar.hide()
        else:
            self.window.set_decorated(True)
            self.window.set_position(gtk.WIN_POS_NONE)
            self.menu_bar.show()

class File(object):
    """A class for accessing the parsed content of a file as
    attributes on an object."""

    def __init__(self, path, create = False): ## add autosync - save everytime an attribute is set - does not work well with list attributes
        self.path = path
        self.attributes = []    ## make this a dict which stores the attributes, instead of adding them as attributes to the File object
        if os.path.exists(path):
            file = open(path)
            self.parse(file)
            file.close()
        elif create:
            self.save()

    def __setattr__(self, name, val):
        if name not in ("path", "attributes") and name not in self.attributes:
            self.attributes.append(name)
        object.__setattr__(self, name, val)

    def __getattr__(self, name):
        try:    return object.__getattribute__(self, name)
        except: return None

    def __delattr__(self, name):
        self.attributes.remove(name)
        object.__delattr__(self, name)

    def parse(self, file):
        def add_attr(type, name, val):
            if type and name and val:
                if   type == "str":  val = val[0]
                elif type == "int":  val = int(val[0])
                elif type == "bool": val = (val[0].lower() == "true")
                setattr(self, name, val)
        type, attr, val = None, "", []
        for line in file.xreadlines():
            line = line.strip()
            if line.startswith("["):
                add_attr(type, attr, val)
                (type, attr), val = line[1:-1].split(":"), []
            elif line:
                val.append(line)
        add_attr(type, attr, val)

    def exists(self):
        return os.path.exists(self.path)

    def delete(self):
        self.attributes = []
        os.remove(self.path)

    def save(self):
        dir = self.path.rsplit("/", 1)[0]
        if not os.path.exists(dir):
            os.makedirs(dir)
        file = open(self.path, "w")
        for attr in self.attributes:
            val = getattr(self, attr)
            file.write("[%s:%s]\n" % (str(type(val))[7:-2], attr))
            if type(val) in (list, tuple):
                for i in val:
                    file.write(i + "\n")
            else:
                file.write(str(val) + "\n")
            file.write("\n")
        file.close()

    def save_all(self):
        self.save()

class Directory(object):
    """A class for accessing files, or directories, in a directory as
    attributes on an object."""

    def __init__(self, path):
        self._path = path
        self._nodes = [f for f in os.listdir(path) if "." not in f] if os.path.exists(path) else []
        self._opened_nodes = {}

    def __iter__(self):
        return self._opened_nodes.itervalues()

    def __contains__(self, name):
        return name in self._nodes

    def __getitem__(self, name):
        if name in self._nodes:
            return getattr(self, name)
        raise KeyError(name)

    def __getattr__(self, name):
        if name in self._nodes:
            if name not in self._opened_nodes:
                if os.path.isdir(self.path(name)): self._opened_nodes[name] = Directory(self.path(name))
                else:                              self._opened_nodes[name] = File(self.path(name))
            return self._opened_nodes[name]
        return object.__getattribute__(self, name)

    def __delattr__(self, name):
        if name in self._nodes:
            self._nodes.remove(name)
            if name in self._opened_nodes:
                self._opened_nodes.pop(name).delete()
        else:
            object.__delattr__(self, name)

    def delete(self):
        for n in self._nodes:
            getattr(self, n).delete()
        self._opened_nodes = {}
        self._nodes = []
        os.rmdir(self.path())

    def save(self):
        if not self.exists():
            os.makedirs(self.path())

    def save_all(self):
        self.save()
        for name, node in self._opened_nodes.items():
            node.save_all()

    def exists(self):
        return os.path.exists(self.path())

    def move(self, new_path):
        if not self.exists() or os.path.exists(new_path):
            return False
        os.rename(self.path(), new_path)
        self._path = new_path
        return True

    def path(self, *name):
        return os.path.join(self._path, *name)

    def add_dir(self, name):
        if not os.path.exists(self.path(name)):
            self._nodes.append(name)
            self._opened_nodes[name] = Directory(self.path(name))
        return getattr(self, name)

    def add_file(self, name):
        if not os.path.exists(self.path(name)):
            self._nodes.append(name)
            self._opened_nodes[name] = File(self.path(name))
        return getattr(self, name)

class Settings(object):
    def __init__(self):
        self.file = File(FILE_SETTINGS, True)
        if self.file.dirs is None:
            self.file.dirs = []

    def save(self):
        self.file.save()

    def add_dir(self, path):
        if not os.path.exists(path):
            output("Failed to add directory - '%s' does not exist!" % path)
            return
        if path not in self.file.dirs:
            self.file.dirs.append(path)
            self.save()
            output("Added '%s'!" % path)

    def delete_dir(self, dir):
        if path not in self.file.dirs:
            output("Failed to remove directory - '%s' not in list!" % path)
            return
        self.file.dirs.remove(dir)
        self.save()
        output("Removed '%s'!" % path)

    def silent(self, state = None):
        if state is None: return self.file.silent
        else:             self.file.silent = state

    def last_profile(self, val = None):
        if val is None: return self.file.last_profile
        else:           self.file.last_profile = val

    def load_last_profile(self):
        if not self.file.last_profile:
            return False
        load_profile(self.file.last_profile)
        if not profile.exists():
            del self.file.last_profile
            self.save()
            return False
        return True

    def list_manga(self):
        ret = []
        for dir in self.file.dirs:
            if os.path.exists(dir):
                ret += os.listdir(dir)
        return ret

class Profile(object):
    def __init__(self, name):
        self.name = name
        self.dir = Directory(os.path.join(DIR_PROFILES, name))
        self.mangas = self.dir.add_dir("manga")
        self.settings = self.dir.add_file("settings")

    def exists(self):
        return self.dir.exists()

    def delete(self):
        self.dir.delete()

    def rename(self, new_name):
        if not self.dir.move(os.path.join(DIR_PROFILES, new_name)):
            return False
        self.name = new_name
        return True

    def save(self):
        self.dir.save_all()

    def save_page(self, manga):
        if manga.title() not in self.mangas:
            self.mangas.add_file(manga.title())
        file = self.mangas[manga.title()]
        file.page = manga.mark.name
        file.save()

    def load_manga(self, path):
        self.settings.last_read = path
        manga = path.rsplit("/", 1)[-1]
        if manga in self.mangas:
            return Manga(self, path, self.mangas[manga].page)
        return Manga(self, path)

class Manga(object):
    def __init__(self, reader_profile, path, page = None):
        self.reader  = reader_profile
        self.path    = path
        self.pages   = self.load_pages()
        self.mark = Page(self, page) if page else self.first_page()

    def load_pages(self):
        files = [f for f in os.listdir(self.path) if f.rsplit(".", 1)[-1] in ("jpg", "png", "gif", "bmp")]
        return natsorted(files) # check if there's an order file / only load image files

    def first_page(self):
        return Page(self, self.pages[0])

    def last_page(self):
        return Page(self, self.pages[-1])

    def num_pages(self):
        return len(self.pages)

    def index_of(self, page):
        return self.pages.index(page.name)

    def set_mark(self, page):
        self.mark = page
        self.reader.save_page(self)

    def previous(self, page, step = 1):
        return Page(self, self.pages[max(0, self.pages.index(page) - step)])

    def next(self, page, step = 1):
        return Page(self, self.pages[min(len(self.pages) - 1, self.pages.index(page) + step)])

    def title(self):
        return self.path.rsplit("/", 1)[-1]

class Page(object):
    def __init__(self, manga, name):
        self.manga = manga
        self.name = name
        self.path = os.path.join(manga.path, name)

    def previous(self, step = 1):
        return self.manga.previous(self.name, step)

    def next(self, step = 1):
        return self.manga.next(self.name, step)

if __name__ == "__main__":
    init()

    if opts.add:
        path = abs_path(opts.add)
        settings.add_dir(path)

    if opts.delete:
        path = abs_path(opts.delete)
        settings.delete_dir(path)

    if opts.silent:
        settings.silent(True)
    if opts.verbose:
        settings.silent(False)

    if opts.profile:
        load_profile(opts.profile)
        if profile.exists():
            output("Loaded profile '%s'" % profile.name)
        else:
            profile.save()
            output("Created profile '%s'" % profile.name)
    else:
        if settings.load_last_profile():
            output("No profile specified - loading '%s'" % profile.name)
        else:
            user = home.split("/")[-1]
            output("No profile exists - creating one for '%s'" % user)
            load_profile(user)
            profile.save()

    reader = Reader()
    manga_path = abs_path(args[0]) if args else cwd
    if manga_dir(manga_path):
        reader.set_manga(profile.load_manga(manga_path))
    reader.start()

    profile.save()
    settings.save()
