# This file is part of browser, and contains the common classes.
#
# Copyright (C) 2009-2010  Josiah Gordon <josiahg@gmail.com>
#
# browser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" A bunch of miscellaneous classes.

"""

import os
import sys
import string
import subprocess
import json
import threading
from time import strftime, sleep

import gtk
import gobject
import glib
import pango
import urllib2
import urllib

class SearchMenu(gtk.Menu):

    _profile_path = ''

    __gproperties__ = {
            'search-engine' : (gobject.TYPE_STRING, 'search engine', 
                'search engine name', 'google', gobject.PARAM_READWRITE),
            }

    __gsignals__ = {
            'engine-clicked' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (object, gobject.TYPE_STRING,)),
            'get-profile-path' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_STRING, 
                ()),
            }
    
    def __init__(self):
        super(SearchMenu, self).__init__()

        self._search_engine_dict = self._load_engine_dict()
        self._search_engine = self._search_engine_dict.pop('default', 'google')

    def _load_engine_dict(self):
        """ Loads a search engine dictionary from a file.

        """

        search_engine_dict = {
                'google': 'https://www.google.com/search?q=%s',
                'google maps': 'http://maps.google.com/maps?q=%s',
                'scroogle': 'https://ssl.scroogle.org/cgi-bin/nbbwssl.cgi?Gw=%s',
                'cuil': 'http://www.cuil.com/search?q=%s',
                'clusty': 'http://www.clusty.com/search?query=%s',
                'wikipedia': 'http://en.wikipedia.org/wiki/Special:Search/%s',
                'dictionary': 'http://www.thefreedictionary.com/%s',
                'thesaurus': 'http://www.thesaurus.com/browse/%s',
                'linuxsearch (arch)': 'http://linuxsearch.org/?cof=FORID%%3A9&cx=003883529982892832976%%3Anbpkmrypeqk&q=%s&sa=Search&siteurl=linuxsearch.org%%2F&d=Arch',
                'shodan computer search': 'http://www.shodanhq.com/?q=%s', 
                'duck duck go': 'https://duckduckgo.com/?q=%s&kr=-1',
                'ixquick': 'https://www.ixquick.com/do/metasearch.pl?query=%s',
                'default': 'ixquick',
                }
        filename = '%s/search_engines' % SearchMenu._profile_path
        try:
            with open(filename, 'r') as engine_file:
                search_engine_dict = json.loads(engine_file.read())
        except Exception as err:
            print("Error reading engine file using default. %s" % err)
            try:
                with open(filename, 'w') as engine_file:
                    engine_file.write(json.dumps(search_engine_dict, indent=4))
            except Exception as err:
                print("Error writing engine file. %s" % err)

        return search_engine_dict

    def do_get_property(self, prop):
        if prop.name == 'search-engine':
            return self._search_engine

    def do_set_property(self, prop, value):
        if prop.name == 'search-engine':
            self._search_engine = value

    def build_menu(self):
        if self.get_children():
            self.foreach(self.remove)
        for name, search_string in self._search_engine_dict.iteritems():
            menuitem = gtk.ImageMenuItem('gtk-file')
            menuitem.set_label(name.capitalize())
            label = menuitem.get_children()[0]
            if name == self._search_engine:
                # Set the current item to bold italic style
                label.modify_font(pango.FontDescription('bold italic'))
            menuitem.connect('button-release-event', self._menu_item_clicked, 
                    name)
            self.append(menuitem)
        self.show_all()

    def _menu_item_clicked(self, menuitem, event, name):
        menuitem.parent.popdown()
        self.set_property('search-engine', name)
        self.emit('engine-clicked', event, name)
        self.build_menu()

    def _convert_string(self, search_term):
        """ _convert_string(search_term) -> Convert 'search_term' to 
        a valid uri string.

        Not used, because we can just use urllib.quote.

        """

        search_term = search_term.replace('%', '%25')
        for i in string.punctuation + ' ':
            if i not in '.-//_%':
                hexnum = hex(ord(i)).strip('0x').upper()
                if len(hexnum) < 2:
                    hexnum = '%s0' % hexnum
                search_term = search_term.replace(i, '%%%s' % hexnum)
        return search_term

    def get_uri(self, search_term, engine_name=None):
        if engine_name:
            return self._search_engine_dict[engine_name.lower()] % \
                    urllib.quote(search_term)
        else:
            return self._search_engine_dict[
                    self.get_property('search-engine').lower()
                    ] % urllib.quote(search_term)

class SpinnerIcon(gtk.Image):

    def __init__(self, image_size=gtk.ICON_SIZE_MENU):
        super(SpinnerIcon, self).__init__()
        self._frames = []
        icon_theme = gtk.icon_theme_get_default()
        icon_info = icon_theme.lookup_icon('process-working', image_size, 
                gtk.ICON_LOOKUP_USE_BUILTIN)
        if icon_info:
            icon = icon_info.load_icon()
            size = icon_info.get_base_size()
            width = icon.get_width()
            height = icon.get_height()
            for y in xrange(0, height, size):
                for x in xrange(0, width, size):
                    self._frames.append(icon.subpixbuf(x, y, size, size))

        self._current_frame = 0
        self._num_frames = len(self._frames) -1

        icon_theme = gtk.icon_theme_get_default()
        self._default_icon = icon_theme.load_icon('text-html', 
                gtk.ICON_SIZE_MENU, gtk.ICON_LOOKUP_USE_BUILTIN)
        self._default_icon = self._default_icon.scale_simple(16, 16, 
                gtk.gdk.INTERP_BILINEAR)
        self.set_from_pixbuf(self._default_icon)
        self._is_spinning = False

    def _finished(self):
        self.set_from_pixbuf(self._default_icon)

    def _set_frame(self, index):
        if index <= self._num_frames:
            self._current_frame = index
            self.set_from_pixbuf(self._frames[index])

    def _next_frame(self):
        if self._current_frame < self._num_frames:
            self._set_frame(self._current_frame+1)
        else:
            self._set_frame(1)

        return True
    
    def set_default_icon(self, pixbuf):
        self._default_icon = pixbuf
        if not self._is_spinning:
            self._finished()

    def get_default_icon(self):
        return self._default_icon
    
    def is_spinning(self):
        return self._is_spinning

    def start(self, timeout=32):
        self._spinner_event = glib.timeout_add(timeout, self._next_frame)
        self._is_spinning = True

    def stop(self):
        glib.source_remove(self._spinner_event)
        self._is_spinning = False
        self._finished()

class SaveDialog(object):
    """ SaveDialog(filename, folder) -> Provides an object
    that uses a file chooser dialog to save a file, and uses a message
    box to check if files should be overwritten. 
    
    """

    def __init__(self, filename, folder):
        """ SaveDialog(filename, folder) -> Initializes the local variables.
        
        """

        self._folder = folder
        self._filename = filename

    def run(self):
        """ run() -> returns a filename with path
        to save a file to.
        
        """

        return self._save_dialog()

    def get_folder(self):
        """ get_folder() -> Returns the current folder.
        
        """

        return self._folder

    def _overwrite_dialog(self, filename):
        """ _overwrite_dialog(filename) -> Presents the user with a yes no
        dialog asking them if 'filename' should be overwritten, and returns
        the users response.

        """

        message = "File %s already exists.\n\nShould it be overwritten?" % \
                filename
        msg_dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, 
                gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, message)
        msg_dialog.set_response_sensitive(gtk.RESPONSE_YES, True)
        msg_dialog.set_response_sensitive(gtk.RESPONSE_NO, True)
        response = msg_dialog.run()
        msg_dialog.destroy()
        return response

    def _save_dialog(self):
        """ _save_dialog -> Opens a save dialog and allows the user to
        select the filename and folder to save to, and returns the file
        the user selects.

        """

        save_dialog = gtk.FileChooserDialog('Save As...', None, 
                gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, 
                    gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        save_dialog.set_current_name(self._filename)
        save_dialog.set_current_folder(self._folder)
        response = None
        while not response:
            response = save_dialog.run()
            if response == gtk.RESPONSE_OK:
                out_filename = save_dialog.get_filename()
                if os.path.isfile(out_filename):
                    response = self._overwrite_dialog(out_filename)
                    if response == gtk.RESPONSE_YES:
                        self._folder = save_dialog.get_current_folder()
                    else:
                        response = None
                else:
                    self._folder = save_dialog.get_current_folder()
            else:
                out_filename = None

        save_dialog.destroy()
        return out_filename

class OpenDialog(object):
    """ OpenDialog(filename, folder) -> Provides an object
    that uses a file chooser dialog to open a file.
    
    """

    def __init__(self, folder):
        """ OpenDialog(folder) ->
        sets folder
        
        """

        self._folder = folder

    def run(self):
        """ run() -> returns a filename with path
        to open.
        
        """

        return self._open_dialog()

    def get_folder(self):
        """ get_folder() -> Returns the current folder.
        
        """

        return self._folder

    def _error_dialog(self, filename):
        """ _error_dialog(filename) -> Opens an error dialog notifying the
        user that 'filename' does not exist.

        """

        message = "File %s does not exists." % filename
        msg_dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, 
                gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, message)
        msg_dialog.set_response_sensitive(gtk.RESPONSE_CLOSE, True)
        response = msg_dialog.run()
        msg_dialog.destroy()
        return response

    def _open_dialog(self):
        """ _open_diloag -> Displays an Open File dialog and allows the user
        to select the file to open, and returns the file the user selects.

        """

        open_dialog = gtk.FileChooserDialog('Open...', None, 
                gtk.FILE_CHOOSER_ACTION_OPEN, 
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        open_dialog.set_current_folder(self._folder)
        response = None
        while not response:
            response = open_dialog.run()
            if response == gtk.RESPONSE_OK:
                in_filename = open_dialog.get_filename()
                if not os.path.isfile(in_filename):
                    response = self._error_dialog(in_filename)
                    response = None
                else:
                    self._folder = open_dialog.get_current_folder()
            else:
                in_filename = None

        open_dialog.destroy()

        return in_filename

class StdoutRedirect(object):

    def __init__(self, output_func, *args):
        self._output_func = output_func
        self._args = args
        self._old_stdout = sys.stdout

    def write(self, data):
        if data.strip():
            self._old_stdout.write('%s' % data)
            self._old_stdout.flush()
            self._output_func('(stdout): %s' % data, *self._args)

    def __enter__(self):
        try:
            sys.stdout = self
        except:
            sys.stdout = self._old_stdout
        return self

    def __exit__(self, type, value, tb):
        try:
            sys.stdout = self._old_stdout
        except:
            pass
        return True

class LogView(gtk.ScrolledWindow):
    """ LogView() -> TextView for logging 
    
    """

    def __init__(self, font='', font_size=10):
        """ LogView(font='Terminus', font_size=10) -> Create a scrolled text
        view for logging debug output of the browser.

        """

        super(LogView, self).__init__()

        self._icon = gtk.Image()
        self._icon.set_from_icon_name('utilities-terminal', 
                gtk.ICON_SIZE_MENU)
        self._title = "Debug Console"

        # Set the scrollbars visibility to automatic
        self.set_policy('automatic', 'automatic')

        # Set the shado the point in.
        self.set_shadow_type(gtk.SHADOW_IN)

        self._text_view = gtk.TextView()
        #self._text_view.modify_font(pango.FontDescription('%s %s' % (font, 
            #font_size)))
        self._text_view.set_editable(False)
        self._text_view.set_cursor_visible(False)
        self._text_view.set_wrap_mode(gtk.WRAP_CHAR)

        self._text_buffer = self._text_view.get_buffer()
        self._tag_table = self._text_buffer.get_tag_table()

        # Set a default tag used for everything.  So unless it is overridden
        # the same font and font_size is used everywhere.
        self._text_buffer.create_tag('default', font=font, 
                size_points=font_size)

        self.add(self._text_view)

        # Setup the default tags.
        self._setup_tags()

        self.show_all()

        # The lock used to keep messages from becoming scrambled.
        self._lock = threading.Lock()

        # Create a right-gravity mark to scroll to the end.
        end = self._text_buffer.get_end_iter()
        self._end_mark = self._text_buffer.create_mark('end', end, False)

        # Dictionaries for converting from ansi color to tag names.
        self._tag1_dict = {
                32: 'tab',
                34: 'main',
                }

        self._tag2_dict = {
                '38;5;64': 'uri',
                '38;5;69': 'movie',
                '38;5;88': 'plugin',
                '38;5;96': 'warning',
                '38;5;56': 'download',
                '38;5;69': 'resource',
                '38;5;93': 'navigation',
                '38;5;64': 'new-window',
                '38;5;202': 'mime',
                '38;5;180': 'pid',
                '38;5;193': 'wave',
                '38;5;178': 'title',
                '38;5;138': 'favicon',
                '38;5;175': 'send-uri',
                '38;5;196': 'console-msg',
                '1;38;5;196': 'block',
                }

    def _setup_tags(self):
        """ _setup_tags -> Add the default tags to the text buffer.

        """

        # Make a dictionary of the tag : tab properties for the debug text 
        # view.
        tag_dict = {
                'tab': {'foreground': '#4E9A06'},
                'pid': {'foreground': '#D7AF87'},
                'uri': {'foreground': '#5F8700'},
                'main': {'foreground': '#3465A4'},
                'mime': {'foreground': '#FF5F00'},
                'wave': {'foreground': '#B9E092'},
                'movie': {'foreground': '#5F87FF'},
                'title': {'foreground': '#D7AF00'},
                'block': {'foreground': '#FF0000', 
                    'weight': pango.WEIGHT_BOLD},
                'plugin': {'foreground': '#870000'},
                'warning': {'foreground': '#875F87'},
                'favicon': {'foreground': '#AF8787'},
                'send-uri': {'foreground': '#D787AF'},
                'download': {'foreground': '#5F00D7'},
                'resource': {'foreground': '#5F87FF'},
                'date-time': {'foreground': '#5fafff'},
                'navigation': {'foreground': '#8700FF'},
                'new-window': {'foreground': '#5F8700'},
                'console-msg': {'foreground': '#FF0000'},
                }

        # Add the tags from the dictionary to the text view.
        for tag_name, properties in tag_dict.iteritems():
            self.add_tag(tag_name, **properties)

    def _append_text_with_tag_name(self, text, tag_name=None):
        """ _append_text_with_tab_name(text, tab_name=None) -> Append 'text'
        to the text view.  If the view is scrolled to the bottom before the
        text is added than scroll it to the bottom after adding it, otherwise
        just leave it where it was.

        """

        # Get the 'y' position of the last visible line.
        visible_rect = self._text_view.get_visible_rect()
        visible_y = visible_rect.y + visible_rect.height

        end = self._text_buffer.get_end_iter()

        # Get the last 'y' posisiton of the last line.
        end_y = self._text_view.get_line_yrange(end)

        tag_name_list = ['default']
        if tag_name:
            tag_name_list.append(tag_name)
        self._text_buffer.insert_with_tags_by_name(end, text, *tag_name_list)

        # Scroll on output if the last line is visible, or the views parent
        # is not visible.
        if sum(end_y) <= visible_y or not self.parent.get_property('visible'):
            # Scroll to the end of the buffer.
            self._text_view.scroll_mark_onscreen(self._end_mark)

    def add_tag(self, tag_name, **tag_properties):
        """ add_tab(tab_name, **tag_properties) -> Add a new tag 'tag_name'
        with the properties from 'tag_properties.'

        """

        self._text_buffer.create_tag(tag_name, **tag_properties)

    def set_tag_property(self, tag_name, property, value):
        """ set_tag_property(tag_name, property, value) -> Set the property
        'property' of tag 'tag_name' to the value 'value.'

        """

        self._tag_table.lookup(tag_name).set_property(property, value)

    def log_message(self, message, color=None, data_color=None):
        """ log_message(message, color=None, data_color=None) -> Log
        messages.

        Split the message at colons into two or three pieces.  Use the first
        color on the first piece, the second color on the second piece and no 
        color on the third piece.  Add the date and time to the start of the 
        message.

        """

        tag_name1 = self._tag1_dict.get(color, None)
        tag_name2 = self._tag2_dict.get(data_color, data_color)

        if tag_name2 == '':
            tag_name2 = None

        date = strftime('%h %e %H:%M:%S')
        message_group = [('%s ' % date, 'date-time')]

        message_list = message.split(':',2 )
        if message_list[1:]:
            message_group.append((message_list[0], tag_name1))
            message_group.append((':', None))
            message_group.append((message_list[1], tag_name2))
            if message_list[2:]:
                message_group.append((':%s' % ''.join(message_list[2:]), None))
        else:
            message_group.append((message, None))

        message_group.append(('\n', None))

        self._lock.acquire()
        for msg_tup in message_group:
            glib.idle_add(self._append_text_with_tag_name, *msg_tup)
        self._lock.release()

    def write(self, data):
        """ write(data) -> A write method so we can use a LogView instead of
        a file.

        """

        self.log_message(data)

    def get_icon(self):
        """ get_icon() -> Return the icon.

        """

        return self._icon

    def get_title(self):
        """ get_title -> Return the title.

        """

        return self._title

    def close(self):
        """ close -> Return False so TabBase will leave this tab open.

        """

        return False

class Config(object):
    """ A Config file object for loading/saving config files.

    """

    def __init__(self, filename):
        """ Config(filename) -> Loads and saves configurations from
        'filename.'  The configuration is a jsoned dictionary.

        """

        self._filename = filename
        self._config_dict = {}
        self._load()

    def get_setting(self, name, default=True):
        """ get_setting(name) -> Returns the value of the setting or default
        if the setting is not added.

        """

        return self._config_dict.get(name, default)

    def set_setting(self, name, value, overwrite=True, save=False):
        """ set_setting(name, value, overwrite=True, save=False) -> Add/Set 
        the specified setting to the configuration dictionary.  Only overwrite
        the settings value if overwrite is True.  Save if save is True.

        """

        if overwrite or (name not in self._config_dict):
            self._config_dict[name] = value

        if save:
            self.save()

    def remove_setting(self, name):
        """ remove_setting(name) -> Removes the specified setting, returning
        its value.  If 'name' is not in the config than return None.

        """

        return self._config_dict.pop(name, None)

    def _load(self):
        """ _load -> Initializes the config dictionary from a file.

        """

        try:
            with open(self._filename, 'r') as config_file:
                self._config_dict = json.loads(config_file.read())
        except IOError as err:
            # Create the config file if it does not exist.
            print("Error loading config %s: %s" % (self._filename, err))
            print("Creating empty config.")
            self._config_dict = {}
            self.save()
        except Exception as err:
            print("Error loading config %s: %s" % (self._filename, err))
            self._config_dict = {}

    def save(self):
        """ save -> Jsons the config dictionary and writes it to a file.

        """

        try:
            with open(self._filename, 'w') as config_file:
                config_file.write(json.dumps(self._config_dict, indent=4))
        except Exception as err:
            print("Error writing config to file %s: %s" % (self._filename, 
                err))

