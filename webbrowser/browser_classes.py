# This file is part of browser, and contains the base classes for the main 
# window and the tabs.
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

""" Generic base classes for a browser window and tab.

The classes in this file are not meant to be use independently.  They should
be used as a base for their respective browser parts.

BrowserTabBase contains most of the functionality of the browser tab, only the
interaction between it and the main browser view is missing and should be
supplied by the inheritor.

BrowserBase contains the implementation independent functionality for the main
browser window.

"""

import os
import sys
import tempfile
import json
import threading
import re
from time import strftime
from subprocess import Popen

import Image, cStringIO
import gtk
import gobject
import glib
import pango
import urllib
#import urllib2
import dbus.service

import bookmarks
from classes import SpinnerIcon, SearchMenu
from tab_classes import BrowserTabs, TerminalTabs, TabList
from file_watch import FileWatcher
from embed_sock import EmbedApp
from download_classes import DownloadManager
from functions import redirect_warnings
from plugin_loader import Plugins
from findbar import FindBar
from defaults import APP_NAME

# Set the global message sender-name color.
MSGCOLOR = 34

class BrowserTabBase(gtk.VBox):
    """ BrowserTabBase -> The browser tab base class. 
    
    """

    # Custom gobject signals that can be emitted
    __gsignals__ = {
            'title-changed' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
            'browser-new-tab' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, (gobject.TYPE_PYOBJECT,)),
            'print-message' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_STRING)),
            'popup-bookmark-menu' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
            'toggle-download-manager' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, ()),
            'toggle-tab-manager' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, ()),
            'save-tabs' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
            'download-uri' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING, gobject.TYPE_STRING)),
            'embed-mime-uri' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING, gobject.TYPE_STRING, 
                    gobject.TYPE_STRING)),
            'hover-uri': (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
            }

    def __init__(self, popup=False, uri=None, history_str='', 
            history_index=1, profile='default'):
        """ BrowserTabBase(popup=False, uri=None, history_str='', 
        history_index=1) ->
        Base class for browser tabs 
        popup - if tab was created from a popup (opened in the background)
        uri - uri to open in newly created tab
        history_str - string containing the history to be used 
        history_index - index in copied history to load 
        profile - The profile to save settings and bookmarks to.
        
        """

        super(BrowserTabBase, self).__init__()

        # Define variables
        self._profile = profile
        self._popup = popup
        self._uri = uri
        self._history_index = history_index
        self._page_loading = False
        self._history_str = history_str
        self._favicon_lock = threading.Lock()
        self._protocol_pat = re.compile(
                '^(about:|http://|https://|file://|ftp://|javascript:|mailto:)', re.I)
        self._type = None

        self._active_tab = False

        # The pop-up menu to hold the back forward history.
        self._history_menu = gtk.Menu()

        self._title = 'Blank page'

        self._favicon_file = '/tmp/browser_icon_%s.icon' % \
                tempfile._get_candidate_names().next()

        # Spinning working icon
        self._spinner_icon = SpinnerIcon()

        # Setup search engine menu
        self._search_engine_menu = SearchMenu()
        self._search_engine_menu.connect('notify::search-engine', 
                self._search_engine_notify)
        self._search_engine_menu.build_menu()

        # Setup address bar
        self._setup_address_bar()
        self.connect('grab-focus', lambda *a: self._address_entry.grab_focus())

        # Make find bar
        self._find_bar = FindBar()
        self._setup_find_bar()

        #self._status_bar = gtk.Statusbar()

        # Setup layout of tab
        self.pack_start(self._address_bar, False) 
        self.pack_start(self._find_bar, False)
        #self.pack_end(self._status_bar, False)

        self.set_homogeneous(False)

    def close(self):
        """ close() -> cleans up and closes tab 
        
        """

        # Remove the icon file if it still exists.
        self._remove_icon_file()

        return self.do_close()

    def do_close(self):
        """ do_close() -> to be implemented by inheritor 
        
        """

        return True

    @property
    def active_tab(self):
        """ Whether this tab is active.

        """

        return self._active_tab

    @active_tab.setter
    def active_tab(self, value):
        """ Set whether this tab is active.

        """

        self._active_tab = value

    @property
    def type(self):
        """ The type of the tab.

        """

        return self._type

    def take_focus(self):
        """ take_focus -> Take keybaord focus.

        """

        pass

    def get_history_index(self):
        """ get_history_index() -> Returns the current pages index in the back
        forward history of the tab. 
        
        """

        if not self._history_str:
            return 0
        else:
            return json.loads(self._history_str)[0]

    def get_icon(self):
        """ get_icon() -> returns tab icon 
        
        """

        return self._spinner_icon

    def get_history_str(self):
        """ get_history_str -> Return a valid history str.

        """

        if not self._history_str:
            return '[]'

        return self._history_str

    def get_save_list(self):
        """ get_save_list() -> Get the information necessary to restore the 
        tab.

        Deprecated.  Use get_save_dict instead.

        """

        return ['', json.loads(self.get_history_str())]

    def get_save_dict(self):
        """ get_save_dict() -> Get the information necessary to restore the 
        tab.

        """

        return {'pid':'', 'history':json.loads(self.get_history_str())}

    def do_get_history(self, index=2):
        """ do_get_history(index=0) -> To be implemented by inheritor.

        """

        pass

    def get_history(self, index=2):
        """ get_history(index=2) -> Returns a list with the current history 
        index followed by title, uri pairs.  

        """

        history_str = self.do_get_history(index)

        return json.loads(history_str)

    def get_uri(self):
        """ get_uri() -> returns tab uri 
        
        """

        return self._uri

    def get_title(self):
        """ get_title() -> returns tab title 
        
        """

        return self._title

    def set_icon(self, pixbuf_icon):
        """ set_icon(pixbuf_icon) -> Set the tabs icon to 'pixbuf_icon.'

        """

        self._spinner_icon.set_default_icon(pixbuf_icon)
        self._address_entry.set_icon_from_pixbuf(0, pixbuf_icon)

    def set_title(self, title):
        """ set_title(title) -> sets tab title 
        
        """

        self._title = title
        self._send_save_tabs()

    def set_uri(self, uri):
        """ set_uri(uri) -> sets tab uri 
        
        """

        self._uri = uri
        self._address_entry.set_text(uri)
        self._send_save_tabs()

    def _remove_icon_file(self):
        """ Remove the favicon file.

        """

        favicon_file = self._favicon_file
        if os.path.isfile(favicon_file):
            os.unlink(favicon_file)

    def _send_save_tabs(self):
        """ _send_save_tabs() -> Updates the tab history string and emits the
        save-tabs signal.

        """

        self._history_str = self.do_get_history()
        self.emit('save-tabs')
    
    def zoom(self, direction):
        """ zoom(direction) -> Zoom in if direction is 1 otherwise zoom out.

        """

        self.do_zoom(direction)

    def print_page(self):
        """ print_page() -> to be implemented by inheritor 
        
        """

        pass

    def print_message(self, message, color=0, data_color=''): 
        """ print_message(message, color=0, data_color='') ->
        emits 'print-message' signal so the tabs parent can handle 
        message printing 
        
        """

        self.emit('print-message', message, color, data_color)

    def do_receive_hover_uri(self, uri):
        """ do_receive_hover_uri(uri) -> handles hover uris when they 
        are received (i.e. putting them in the status bar)
        
        """

        self.emit('hover-uri', uri)
        #if uri != "None":
            #self._status_bar.pop(1)
            #self._status_bar.push(1, uri)
        #else:
            #self._status_bar.pop(1)

    def do_receive_back_forward(self, can_go_back, can_go_forward):
        """ do_receive_back_forward(can_go_back, can_go_forward) ->
        changes the tab toolbar history button based on if the tab
        has back-forward history 
        
        """

        self.toggle_back_forward(can_go_back, can_go_forward)
        self.populate_history_menu()

    def do_receive_title(self, title):
        """ do_receive_title(title) -> handles received titles 
        (i.e. sets tab title, and emits 'title-changed' so the
        tabs parent can know when the title changes) 
        
        """

        if title != self.get_title():
            self.set_title(title)
            self.emit('title-changed', title)

    def do_receive_uri(self, uri):
        """ do_receive_uri(uri) -> If the received uri is not None and
        it is not the same as the tabs uri then set the tabs uri to uri 
        
        """

        if uri != 'None' and uri != self.get_uri():
            self.set_uri(uri)

    def do_receive_favicon_uri(self, icon_uri):
        """ do_receive_favicon_uri(icon_uri) -> download the favicon from
        icon_uri.  If it is a valid icon, set the tab icon to it, otherwise
        set it to a default icon. 
        
        """

        # A list holding the different uri's to try.
        uri_list = []

        # If the icon uri ends with a '/' then set it to a default value.
        if icon_uri:
            if icon_uri[-1] == '/':
                icon_uri = '/favicon.ico'
        

        # Add the icon to the list.
        uri_list.append(icon_uri)

        # Get the tabs current uri (i.e. icon parent).
        #uri = self.get_uri()

        # Split up parent uri
        #sr = urllib2.urlparse.urlsplit(uri)

        # Set alternative uris in case the one fails.
        #uri_list.append('%s://%s/favicon.ico' % (sr.scheme, sr.netloc))

        #if sr.netloc.count('.') > 1:
            #uri_list.append('%s://%s/favicon.ico' % 
                    #(sr.scheme, sr.netloc.split('.', 1)[1]))

        # Add a uri for 'http' if the scheme is 'https'
        #if sr.scheme == 'https':
            #uri_list.append('http://%s/favicon.ico' % (sr.netloc))

        # If the icon uri begins with a '/' it is a relative path
        #if icon_uri[0] == '/' or icon_uri[0:2] == '..':
            #uri_list.append('%s://%s%s' % (sr.scheme, sr.netloc, icon_uri))

            # Add a uri for 'http' if the scheme is 'https'
            #if sr.scheme == 'https':
                #http_favicon_uri = 'http://%s%s' % (sr.netloc, icon_uri)
        #else:
            # The icon uri is an absolute path
            #uri_list.append(icon_uri)
    
        # Remove the icon file if it still exists.
        self._remove_icon_file()

        # Start a new thread to download the favicon.
        download_thread = threading.Thread(target=self._download_favicon, 
                args=(uri_list, self._favicon_file))

        # Make the thread a daemon so it won't stop the main program 
        # from exiting
        download_thread.daemon = True
        download_thread.start()

    def do_receive_progress(self, progress):
        """ do_receive_progress(progress) -> Handle the progress of
        the page loading.
        
        """

        # Enable the stop/refresh button.
        self._stop_ref_button.set_sensitive(True)

        self._set_progress(progress)

        # Stop the working icon and progress bar when the page is loaded.
        if progress == 1:
            self._spinner_icon.stop()
            self._set_progress(0)
            self.set_loading(False)
            # If this is the active tab then grab the focus.
            if self.active_tab:
                self.take_focus()
        else:
            # Show progress and working icon when the page is loading.
            if not self._spinner_icon.is_spinning():
                self._spinner_icon.start()
            self.set_loading(True)
    
    def _download_favicon(self, uri_list, favicon_file):
        """ _download_favicon(uri_list, favicon_file) -> A thread to download
        the favicon from a uri in 'uri_list' to 'favicon_file.'

        """


        # Use a lock so the favicon file isn't overwritten before it can load.
        self._favicon_lock.acquire()

        #icon_grabber = urllib.FancyURLopener()

        # Try all icon uris
        for uri in uri_list:
            self.print_message(
                    'browser tab: Attempting to load %s as favicon.' % uri, 
                    MSGCOLOR)
            try:    
                try:
                    import urllib2
                    # Save icon to 'favicon_file'
                    #icon_grabber.retrieve(uri, favicon_file)

                    #icon_reader = urllib.urlopen(uri)
                    opener_list = [urllib2.HTTPHandler, urllib2.HTTPSHandler]
                    icon_opener = urllib2.build_opener(*opener_list)
                    icon_reader = icon_opener.open(uri)
                    with open(favicon_file, 'w') as icon_file:
                        icon_file.write(icon_reader.read())
                    icon_reader.close()
                    icon_opener.close()
                except Exception as err:
                    #print("error loading icon %s is %s" % (uri, err))
                    icon_grabber = Popen(['wget', '-q', uri, '-O', 
                                          favicon_file])
                    icon_grabber.wait()

                pixbuf_icon = gtk.gdk.pixbuf_new_from_file(favicon_file)
                pixbuf_icon = pixbuf_icon.scale_simple(16, 16, 
                        gtk.gdk.INTERP_BILINEAR)

                # If this icon succeeds then exit, don't try the next.
                break
            except Exception as err:
                # The uri failed to load a valid icon so use the default 
                # 'text-html' icon
                try:
                    icon_theme = gtk.icon_theme_get_default()
                    pixbuf_icon = icon_theme.load_icon('text-html', 
                            gtk.ICON_SIZE_MENU, gtk.ICON_LOOKUP_USE_BUILTIN)
                except:
                    pass

                self.print_message('browser tab: Failed to load icon: %s with error (%s)' \
                                    % (uri, err), MSGCOLOR)
                #print("error loading icon %s is %s" % (uri, err))
                uri = 'text-html'

        self.print_message(
                'browser tab: Using icon %s as favicon.' % uri, 
                MSGCOLOR)

        # Set the tab icon and address_entry icon to the favicon that worked.
        glib.idle_add(self.set_icon, pixbuf_icon)

        # The icon file is no longer needed so remove it.
        self._remove_icon_file()

        # Release the lock so the next favicon can be downloaded.
        self._favicon_lock.release()

    def _pixbuf_from_uri(self, uri):
        """ _pixbuf_from_uri(uri) -> Trys to load a favicon into a variable
        and load that data into a pixbuf 
        
        """

        icon_data = urllib.urlopen(uri).read()
        icon = Image.open(cStringIO.StringIO(icon_data)).convert('RGBA')
        icon = icon.resize((16,16))
        pixbuf_icon = gtk.gdk.pixbuf_new_from_data(icon.tostring(), 
                gtk.gdk.COLORSPACE_RGB, True, 8, icon.size[0], icon.size[1], 
                icon.size[0]*4)
        #mode = icon.mode
        #if mode == 'RGB':
            #icon = icon.convert('RGBA')
            #icon_str = '\x00\x00\x00\x00'.join(icon.tostring()
            #icon_str = icon_str.split('\x00\x00\x00\xff'))
            #isrgba = True
            #rowstride = icon.size[0]*4
        #else:
            #icon = icon.convert('RGB')
            #icon_str = icon.tostring()
            #isrgba = False
            #rowstride = icon.size[0]*3
        #pixbuf_icon = gtk.gdk.pixbuf_new_from_data(icon_str, 
                #gtk.gdk.COLORSPACE_RGB, isrgba, 8, icon.size[0], 
                #icon.size[1], rowstride)
        return pixbuf_icon

    def _toolbar_button(self, icon_name, sensitive, tooltip_text, callback, 
            *user_args):
        """ _toolbar_button(icon_name, sensitive, tooltip_text, callback, 
        *user_args) -> Creates and returns a toolbar button.
        icon_name - The icon (can be a name or an image)
        sensitive - Whether the button should be enabled
        tooltip_text - The tooltip text
        callback - The function to call when the button is clicked
        *user_args - Optional arguments to pass to the callback function 
        
        """

        button = gtk.Button()

        # Load the icon from icon_name unless it is an image
        if type(icon_name) == str:
            image = gtk.Image()
            image.set_from_icon_name(icon_name, gtk.ICON_SIZE_LARGE_TOOLBAR)
            button.set_image(image)
        else:
            button.add(icon_name)

        button.set_relief(gtk.RELIEF_NONE)
        button.set_sensitive(sensitive)
        button.set_tooltip_text(tooltip_text)
        button.connect('button-release-event', callback, *user_args)

        return button

    def _setup_address_bar(self):
        """ _setup_address_bar() -> Build the address bar 
        
        """

        self._address_bar = gtk.Toolbar()
      
        # A tuple of the history and stop/refresh button layout
        history_button_tup = (
                ('_back_button', ('back', False, 'Go back in history', 
                    self._back_forward_clicked)),
                ('_forward_button', ('forward', False, 
                    'Go forward in history', self._back_forward_clicked)),
                ('_history_menu_button', (gtk.Arrow(gtk.ARROW_DOWN, 
                    gtk.SHADOW_OUT),
                    False, 'Go forward or back in  history', 
                    self._history_menu_button_clicked)),
                ('_stop_ref_button', ('refersh', False, 
                    'Refresh page (Middle click to copy tab, Shift Middle click to duplicate tab)', 
                    self._stop_ref_clicked))
                )

        # Create buttons from the tuple
        for (button_name, settings) in history_button_tup:
            self.__setattr__(button_name, self._toolbar_button(*settings))
            item = gtk.ToolItem()
            item.add(self.__getattribute__(button_name))
            self._address_bar.add(item)

        # Set the current state of the stop/refresh button
        self.set_stop_ref('gtk-refresh')

        # Setup the address entry
        self._address_entry = gtk.Entry()
        self._address_entry.set_icon_from_icon_name(0, 'text-html') 
        self._address_entry.set_icon_from_icon_name(1, 'go-jump') 
        self._address_entry.set_tooltip_text('Enter address here')
        self._address_entry.set_icon_tooltip_text(0, 'Open bookmarks menu')
        self._address_entry.set_icon_tooltip_text(1, 'Load uri in address bar')
        self._address_entry.connect('activate', self._go_to)
        self._address_entry.connect('icon-release', self._address_icon_release)
        self._address_entry.connect('drag-data-received', 
                self._address_drag_data_received)
        self._address_entry.connect('drag-drop', 
                self._address_drag_drop)
        self._address_entry.drag_dest_set(gtk.DEST_DEFAULT_ALL,
                [('text/plain', 0, 0)], gtk.gdk.ACTION_COPY)

        # Load the tabs uri (if there is one) into the entry
        if self._uri:
            self._address_entry.set_text(self._uri)

        # Toolbar item for the address entry
        entry_item = gtk.ToolItem()
        entry_item.set_expand(True)
        entry_item.add(self._address_entry)

        self._address_bar.add(entry_item)

        self._address_bar.add(gtk.SeparatorToolItem())

        # Setup the download button
        download_button = self._toolbar_button('emblem-downloads', True, 
                'Toggle Download Manager', self._download_button_clicked)
        download_item = gtk.ToolItem()
        download_item.add(download_button)
        self._address_bar.add(download_item)

        # Setup the tab menu button
        tab_menu_button = self._toolbar_button('document-open-recent', True, 
                'Toggle closed tab manager', self._tab_menu_button_clicked)
        tab_menu_item = gtk.ToolItem()
        tab_menu_item.add(tab_menu_button)
        self._address_bar.add(tab_menu_item)

        self._address_bar.add(gtk.SeparatorToolItem())

        # Setup the search entry
        self._search_entry = gtk.Entry()
        self._search_entry.set_width_chars(25)
        self._search_entry.set_tooltip_text('Enter search string here')
        self._search_entry.set_icon_from_icon_name(0, 'gtk-file') 
        self._search_entry.set_icon_from_icon_name(1, 'search') 
        self._search_entry.set_icon_tooltip_text(0, 'Select search engine')
        self._search_entry.set_icon_tooltip_text(1, 'Search')
        self._search_entry.connect('icon-release', self._search_icon_release)
        self._search_entry.connect('activate', self._search_for)
        self._search_entry.connect('focus-in-event', 
                self._search_entry_focus_in)
        self._search_entry.connect('focus-out-event', 
                self._search_entry_focus_out)

        # Toolbar item for the search entry
        entry_item = gtk.ToolItem()
        entry_item.add(self._search_entry)
        self._address_bar.add(entry_item)

        # Set the search entry to empty
        self._search_empty = True
        engine_name = self._search_engine_menu.get_property('search-engine')
        self._set_search_empty_text(engine_name)

        self._address_bar.set_style('icons')

    def set_address_completion(self, completion_model):
        """ set_address_completion(completion_model) -> Set the address 
        completion of the address entry to use completion model 
        
        """

        address_completion = gtk.EntryCompletion()

        # Setup up callback when a match is selected
        address_completion.connect('match-selected', self._completion_match)
        #address_completion.connect('cursor-on-match', self._completion_match)

        text_cell = gtk.CellRendererText()
        address_completion.pack_start(text_cell, False)
        address_completion.set_text_column(0)

        address_completion.set_model(completion_model)

        address_completion.set_popup_completion(True)

        # Make the entry auto complete in line
        #address_completion.set_inline_completion(True)  

        address_completion.set_inline_selection(True)

        self._address_entry.set_completion(address_completion)

    def _completion_match(self, address_completion, completion_model, iter):
        """ _completion_match(address_completion, completion_model, iter) ->
        The function that is called when a match is selected from the 
        completion list. 
        
        """

        # Get uri from row(iter) column(1)
        uri = completion_model.get_value(iter, 1)

        # Set the address to uri
        self._address_entry.set_text(uri)

        # Load the uri
        self.load_uri(uri)

        return True

    def _search_engine_notify(self, search_engine_menu, search_engine):
        """ _search_engine_notify(search_engine_menu, search_engine) ->
        This function is called when the search engine is changed 
        from the menu
        
        """

        name = search_engine_menu.get_property(search_engine.name).lower()

        # Set the search entry empty text
        self._set_search_empty_text(name)

    def focus_address_entry(self):
        """ focus_address_entry() -> Set the input focus to the 
        address entry 
        
        """

        self._address_entry.grab_focus()

    def focus_search_entry(self):
        """ focus_search_entry() -> Set the input focus to the search entry 
        
        """

        self._search_entry.grab_focus()

    def _set_progress(self, progress):
        """ _set_progress(progress) -> Update the address entry progress 
        bar 
        
        """

        self._address_entry.set_progress_fraction(progress)

    def _address_drag_drop(self, address_entry, context, x, y, timestamp):
        """ Load what was dropped in the address entry.

        """

        self._go_to()
        return True

    def _address_drag_data_received(self, address_entry, context, x, y, 
            selection, target_type, timestamp):
        """ Clear the address entry so new text can be dropped in it.

        """

        if target_type == 0:
            uri = selection.data
            self._address_entry.set_text('')
            context.drag_status(gtk.gdk.ACTION_COPY, timestamp)
            context.drop_finish(True, timestamp)
        else:
            context.drop_finish(False, timestamp)

    def _address_icon_release(self, address_entry, position, event):
        """ _address_icon_release(address_entry, position, event) -> Called
        when the mouse button is released on after clicking one of the icons
        in the address entry. 
        
        """

        if position == gtk.ENTRY_ICON_SECONDARY:
            if event.button == 2:
                # Get selected text (primary clipboard)
                clipboard = gtk.clipboard_get(selection='PRIMARY')
                clipboard_text = clipboard.wait_for_text()

                # Load selection
                if clipboard_text:
                    # Load selected text in address entry
                    self._address_entry.set_text(clipboard_text)

            # Load uri if the right(secondary) icon is clicked
            self._go_to()
        else:
            # Pop up the bookmark-menu when it left(primary icon is clicked
            self.emit('popup-bookmark-menu', event)

    def _set_search_empty_text(self, text):
        """ _set_search_empty_text(text) -> Set the text to display the
        search entry when it is empty. 
        
        """

        if self._search_empty:
            # Set the text to italic
            self._search_entry.modify_font(pango.FontDescription('italic'))
            self._search_entry.set_text(text.lower().capitalize())
        
    def _search_icon_release(self, search_entry, position, event):
        """ _search_icon_release(search_entry, position, event) -> Called when
        the mouse button is released after clicking one of the icons in the 
        search entry. 
        
        """

        if position == gtk.ENTRY_ICON_PRIMARY:
            # Pop up the search engine menu when the left (primary) icon 
            # is clicked
            self._search_engine_menu.popup(None, None, None, event.button, 
                    event.time, None)
        else:
            if event.button == 2:
                # Get selected text (primary clipboard)
                clipboard = gtk.clipboard_get(selection='PRIMARY')
                clipboard_text = clipboard.wait_for_text()

                # Load selection
                if clipboard_text:
                    # Load selected text in address entry
                    self._reset_search_entry(clipboard_text)

            # Search when the right (secondary) icon is clicked
            self._search_for()

    def _search_entry_focus_in(self, search_entry, event):
        """ _search_entry_focus_in(search_entry, event) -> Called when the
        search entry receives input focus. 
        
        """

        self._reset_search_entry()

    def _reset_search_entry(self, text=''):
        """ _reset_search_entry(text=None) -> Un-italicize and clear the
        search entry if it is supposed to be empty.  Set the search entry 
        text to text.

        """

        # Set the text to non italic
        self._search_entry.modify_font(pango.FontDescription(''))
        if text:
            self._search_entry.set_text(text)
            self._search_empty = False

        if self._search_empty:
            # Set it to empty if it was empty
            self._search_entry.set_text('')

    def _search_entry_focus_out(self, search_entry, event):
        """ _search_entry_focus_out(search_entry, event) -> Called when the
        search entry loses input focus. 
        
        """

        text = search_entry.get_text()
        if not text:
            self._search_empty = True
            # Set the search entry to the search engine name when it is empty
            engine_name = \
                    self._search_engine_menu.get_property('search-engine')
            self._set_search_empty_text(engine_name)
        else:
            self._search_empty = False

    def _search_for(self, *args):
        """ _search_fore(*args) -> Called to search for the text in the search
        entry 
        
        """

        if not self._search_empty:
            search_string = self._search_entry.get_text()
        else:
            search_string = ''
        search_uri = self._search_engine_menu.get_uri(search_string)
        self.load_uri(search_uri)

    def _new_tab(self, uri, history_index, flags):
        """ _new_tab(uri, history_index, flags) -> Base function for creating 
        a new tab. 
        
        """

        # Ask for a new tab and return it.
        return self.emit('browser-new-tab', {'uri':uri, 'flags':flags, 
            'history_index':history_index})

    def do_zoom(self, direction):
        """ do_zoom(direction) -> To be implemented by inheritor 
        
        """

        pass

    def do_get_current_item(self):
        """ do_get_current_item() -> To be implemented by inheritor 
        
        """

        return None, 1

    def do_get_back_item(self):
        """ do_get_back_item() -> To be implemented by inheritor 
        
        """

        return None, 1

    def do_get_forward_item(self):
        """ do_get_forward_item() -> To be implemented by inheritor 
        
        """

        return None, 1

    def do_get_history_item(self, index):
        """ do_get_history_item() -> To be implemented by inheritor 
        
        """

        return None, 1

    def do_go_to_history_item(self, index):
        """ do_go_to_history_item() -> To be implemented by inheritor 
        
        """

        pass

    def do_go_back(self):
        """ do_go_back() -> To be implemented by inheritor 
        
        """

        pass

    def do_go_forward(self):
        """ do_go_forward() -> To be implemented by inheritor 
        
        """

        pass

    def _history_menu_button_clicked(self, history_menu_button, event):
        """ _history_menu_button_clicked -> Called when the history menu
        button is clicked.

        """

        # Pop up history menu based on position returned by _position_func
        self._history_menu.popup(None, None, self._position_func, 
                event.button, event.time, event)

    def _stop_ref_clicked(self, stop_ref_button, event):
        """ _stop_ref_clicked(stop_ref_button, event) -> Called when the
        stop/refresh button is clicked. 
        
        """

        if not self.is_loading():
            if event.button == 2:
                # Duplicate the current tab if it is not loading and the 
                # middle mouse button is used to click the refresh button
                uri, history_index = self.do_get_current_item()
                self._new_tab(uri, history_index, event.state)
            else:
                self.refresh_page()
        else:
            # Stop loading when it is loading
            self.stop_loading()

    def _back_forward_clicked(self, button, event=None):
        """ _back_forward_clicked(button, event=None) -> Called when either
        the back or forward button is clicked. 
        
        """

        if event.button == 2:
            # Duplicate the forward or back page if the middle mouse button
            # is used
            if button == self._back_button:
                uri, history_index = self.do_get_back_item()
            else:
                uri, history_index = self.do_get_forward_item()
            self._new_tab(uri, history_index, event.state)
        else:
            # Go forward or back depending on what button is clicked
            if button == self._back_button:
                self.do_go_back()
            else:
                self.do_go_forward()

    def _history_item_clicked(self, history_item, event, item_tup, menu):
        """ _history_item_clicked(history_item, event, item_tup, menu) -> 
        Called when an item is clicked in the history menu. 
        
        """

        # Pop down the menu to avoid a gdk warning
        menu.popdown()

        uri, index, current_index = item_tup
        if event.button == 2:
            # Duplicate that item in a new tab if the middle button is used
            self._new_tab(uri, index, event.state)
        else:
            # Load that 'index' item from history
            # We need to add the absolute of the current_index to 'index' to
            # get the correct index in the current tabs history.
            self.do_go_to_history_item(index + abs(current_index))

    def load_uri(self, uri):
        """ load_uri(uri) -> Load uri in the browser. 
        
        """

        if uri:
            # Set the address entry to uri
            self._address_entry.set_text(uri)
            
        # Go to what is in address entry
        glib.idle_add(self._go_to)
    
    def do_go_to(self, uri):
        """ do_go_to(uri) -> To be implemented by inheritor. 
        
        """

        pass

    def _go_to(self, *args):
        """ _go_to(*args) -> Base function to process the text in the
        address entry. If it does not look like an address it is used
        as a search term for the currently selected engin.  Otherwise
        determine what protocol (file: or http:) it should be.
        
        """

        # First stop the browser from loading whatever it is loading.
        self.stop_loading()

        # uri is loaded from address entry
        uri = self._address_entry.get_text()    
        if not self._protocol_pat.match(uri):
            if ' ' in uri or '.' not in uri or not uri:
                # uri does not look like an address so use it as a search term
                uri = self._search_engine_menu.get_uri(uri)
            elif uri[0] == '/':
                # uri looks like a file: uri
                uri = 'file://%s' % uri
            else:
                # Since we made it here try it as an http: uri.
                uri = 'http://%s' % uri

        # Call go to function.
        self.do_go_to(uri)

    def is_loading(self):
        """ is_loading() -> Returns True if the page is loading, otherwise 
        returns False. 
        
        """

        return self._page_loading

    def set_loading(self, is_loading):
        """ set_loading(is_loading) -> Sets whether the browser is loading 
        a page or not, and changes the stop/refresh button accordingly. 
        
        """

        self._page_loading = is_loading
        if is_loading:
            self.set_stop_ref('gtk-stop')
        else:
            self.set_stop_ref('gtk-refresh')

    def set_stop_ref(self, value):
        """ set_stop_ref(value) -> Setup the stop/refresh button depending on
        if it is going to be a stop or refresh button. 
        
        """

        # Dictionary to determine the tooltip text
        stop_ref_dict = {
                'gtk-refresh': \
                'Refresh page (Middle click to copy tab, Shift Middle click to duplicate tab)', 
                'gtk-stop':'Stop loading page'
                }
        self._stop_ref_button.get_image().set_from_stock(value, 
                gtk.ICON_SIZE_LARGE_TOOLBAR)
        self._stop_ref_button.set_tooltip_text(stop_ref_dict[value])

    def refresh_page(self):
        """ refresh_page() -> To be implemented by the inheritor. 
        
        """

        pass

    def stop_loading(self):
        """ stop_loading() -> To be implemented by the inheritor. 
        
        """

        pass

    def _download_button_clicked(self, button, event):
        """ _download_button_clicked(button, event) -> Called when the download
        button is clicked. 
        
        """

        self.emit('toggle-download-manager')

    def _tab_menu_button_clicked(self, button, event):
        """ _tab_menu_button_clicked(button, event) -> Called when the tab
        menu button is clicked.

        """

        self.emit('toggle-tab-manager')

    def do_get_history_length(self):
        """ do_get_history_length() -> To be implemented by the inheritor. 
        
        """

        pass

    def do_get_back_forward_item(self, index):
        """ do_get_back_forward_item(index) -> To be implemented by the 
        inheritor. 
        
        """

        pass

    def populate_history_menu(self):
        """ populate_history_menu() -> Run a thread to populate the history
        menu.

        """

        populate_thread = threading.Thread(target=self._populate_history_menu)
        populate_thread.daemon = True
        populate_thread.start()

    def _populate_history_menu(self):
        """ _populate_history_menu() -> Populate the history menu. 
        
        """

        if not self._history_str:
            return

        glib.idle_add(self._history_menu.foreach, self._history_menu.remove)

        current_index, hist_list = json.loads(self._history_str)
        for index, hist_item in enumerate(hist_list):
            title, uri = hist_item
            item_index = index - (len(hist_list) - 1)

            # Create menu item of item 'i'
            item = gtk.ImageMenuItem(title)
            if title:
                item.set_label(title)
            else:
                item.set_label(uri)
            item.set_tooltip_text(uri)
            label = item.get_children()[0]
            label.set_max_width_chars(48)
            label.set_ellipsize(pango.ELLIPSIZE_END)
            icon = gtk.Image()
            if item_index == current_index:
                # Set the current item to bold italic style
                label.modify_font(pango.FontDescription('bold italic'))
                icon.set_from_icon_name('text-html', gtk.ICON_SIZE_MENU)
            elif item_index > current_index:
                # Set forward item icons to 'forward' icon
                icon.set_from_icon_name('forward', gtk.ICON_SIZE_MENU)
            else:
                # Set back item icons to 'back' icon
                icon.set_from_icon_name('back', gtk.ICON_SIZE_MENU)
            item.set_image(icon)
            item.connect('button-release-event', self._history_item_clicked, 
                    (uri, item_index, current_index), self._history_menu)
            glib.idle_add(self._history_menu.prepend, item)

        glib.idle_add(self._history_menu.show_all)

    def _position_func(self, menu, user_data):
        """ _position_func(menu, user_data) -> Calculate and return the
        position that the top left corner of the menu should be located. 
        
        """

        # Pop up the menu at the bottom of the history button
        offset = self._history_menu_button.allocation.height
        return (int(user_data.x_root - user_data.x), int(user_data.y_root - \
                user_data.y) + offset, False)

    def toggle_back_forward(self, can_go_back, can_go_forward):
        """ toggle_back_forward(can_go_back, can_go_forward) -> Toggle the back
        and forward buttons sensitivity based on 'can_go_back', and 
        'can_go_forward' 
        
        """

        self._back_button.set_sensitive(can_go_back)
        self._forward_button.set_sensitive(can_go_forward)
        self._history_menu_button.set_sensitive(can_go_back or can_go_forward)

    def _setup_find_bar(self):
        """ _setup_find_bar() -> Build the toolbar for searching for text on a
        page. 
        
        """

        signal_dict = {
                'find-next': (self.find_on_page, 'next'),
                'find-previous' : (self.find_on_page, 'previous'),
                'highlight-toggled' : (self._highlight_toggled,),
                'match-case-toggled' : (self._match_case_toggled,),
                }
        for signame, callback_tup in signal_dict.iteritems():
            self._find_bar.connect(signame, *callback_tup)

    def findbar_visible(self):
        """ findbar_visible() -> Return whether the findbar is visible. 
        
        """

        return self._find_bar.is_visible()

    def toggle_findbar(self, close_button=None, find_text=None):
        """ toggle_findbar(close_button=None) -> Toggle the visibility of
        the findbar. 
        
        """

        self._find_bar.toggle_visibility(close_button, find_text)

    def do_highlight_toggled(self, find_string, match_case, highlight_match):
        """ do_highlight_toggled(find_string, match_case, highlight_match) ->
        To be implemented by inheritor. 
        
        """

        pass

    def _match_case_toggled(self, find_bar, match_case):
        """ _match_case_toggled(match_case) -> The inheritor should handle
        setting and un-setting the case sensitivity in the browser. 
        
        """

        self.do_set_highlight(self._find_bar.get_text(), 
                match_case, 
                self._find_bar.get_highlight())

    def _highlight_toggled(self, find_bar, highlight_match):
        """ _highlight_toggled(highlight_match) -> The inheritor should handle
        toggling the highlight in the browser. 
        
        """

        self.do_set_highlight(self._find_bar.get_text(), 
                self._find_bar.get_match_case(), 
                highlight_match)

    def do_set_highlight(self, find_string, match_case, highlight):
        """ do_set_highlight(find_string, match_case, highlight) -> To be
        implemented by inheritor. 
        
        """

        pass

    def do_find(self, find_string, match_case, find_direction, wrap_find):
        """ do_find(find_string, match_case, find_direction, wrap_find) -> To
        be implemented by inheritor. 
        
        """

        pass

    def find_on_page(self, find_bar=None, find_string=None, direction='next'):
        """ find_on_page(widget) -> Find text on the page.  Depending on what
        widget was clicked to call this function it either searches forward
        or backward on the page. 
        
        """

        # Text to search for
        if not find_string:
            find_string = self._find_bar.get_text()
        
        # Whether to highlight matches or not
        highlight = (not self._find_bar.get_dynamic()) and \
                self._find_bar.get_highlight()
        self.do_set_highlight(find_string, self._find_bar.get_match_case(), 
                highlight)

        # Find 'find_string' on page
        found = self.do_find(find_string, self._find_bar.get_match_case(), 
                direction != 'previous', self._find_bar.get_wrap())

        if not found:
            # Set stop icon when no text is found
            self._find_bar.set_stop()
        else:
            # Set find icon when text was found
            self._find_bar.set_find()

class BrowserBase(gobject.GObject):
    """ BrowserBase -> Base class for browser. 
    
    """

    # Custom gobject signals that can be emitted
    __gsignals__ = {
            'message' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_BOOLEAN, 
                (gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_STRING)),
            }

    # A set of all the browser windows open.
    window_set = set()

    def __init__(self, uri=None, profile='default', width=1213, height=628):
        """ BrowserBase(uri=None, profile='default', width=1213, 
        height=628) -> Browser base class.
        
        """

        super(BrowserBase, self).__init__()

        self._current_tab = None

        self._save_event = None
        self._path = os.path.dirname(__file__)
        self._profile = profile
        self._tabs_file = '%s/%s/%s/browser_tabs' % \
                (glib.get_user_config_dir(), APP_NAME, profile)

        SearchMenu._profile_path = '%s/%s/%s' % \
                (glib.get_user_config_dir(), APP_NAME, profile)

        # Save stdout.
        self._stdout = sys.stdout

        # Setup gtk style
        gtk.rc_parse_string("""
                    style "murrine-default" {
                        GtkToolbar::shadow_type = GTK_SHADOW_NONE
                        GtkStatusbar::shadow_type = GTK_SHADOW_NONE
                    }
                    """)
        # Setup main window
        self._window = gtk.Window()
        self._window.set_icon_name('web-browser')
        self._window.set_default_size(width, height)
        self._window.set_resizable(True)
        self._window.connect('destroy', self.exit)

        # Setup keyboard shortcuts
        self._accels = gtk.AccelGroup()
        self._window.add_accel_group(self._accels)

        self._setup_accels()

        # Create bookmark menu
        self._bookmark_menu = bookmarks.BookmarksMenu(profile=self._profile)
        self._bookmark_menu.setup_completion_model()
        self._completion_model = self._bookmark_menu.get_completion_model()

        self._setup_bookmark_menu()

        # Setup browser tabs
        self._new_tab_button = gtk.Button()
        image = gtk.Image()
        image.set_from_icon_name('tab-new', gtk.ICON_SIZE_MENU)
        self._new_tab_button.set_image(image)
        self._new_tab_button.connect('button-press-event', 
                lambda b, e: self.do_open_tab(flags=e.state, button=e.button))
        self._new_tab_button.show_all()

        self._browser_book = BrowserTabs(self._tabs_file, 
                action_widget=self._new_tab_button)
        self._setup_browser_book()

        # Setup terminal and download tabs
        self._term_book = TerminalTabs(False)
        self._setup_term_book()


        # Add the status bar.
        self._status_bar = gtk.Statusbar()
        #tab_vbox = gtk.VBox()
        #tab_vbox.pack_start(self._browser_book, True)
        #tab_vbox.pack_end(self._status_bar, False)

        # Setup browser layout
        vpaned = gtk.VPaned()
        vpaned.add1(self._browser_book)
        #vpaned.add1(tab_vbox)
        vpaned.add2(self._term_book)
        vpaned.set_property('position_set', True)
        vpaned.set_position(height - 128)

        vbox = gtk.VBox()
        vbox.pack_start(vpaned, True)
        vbox.pack_end(self._status_bar, False)

        self._window.add(vbox)

        # Add plugin manager.
        self._plugins = Plugins(self, self._profile)

        # Add a file watcher.
        if FileWatcher.check():
            self._file_watcher = FileWatcher()
            #self._file_watcher.add_directory(
                    #'%s/webbrowser' % glib.get_user_config_dir())
        else:
            self._file_watcher = None

    def _setup_term_book(self):
        """ _setup_term_book() -> Creates terminal tabs and adds debug terminal
        and download manager to it. 
        
        """

        self._term_book.set_property('visible', False)

        # Create the download manager
        self._download_manager = DownloadManager()
        self._term_book.new_tab(self._download_manager, True)

        # Create list view for closed tabs.
        self._tab_manager = TabList()
        self._term_book.new_tab(self._tab_manager, True)

        self._tab_manager.connect('reopen-tab', self._reopen_tab)

    def _setup_browser_book(self):
        """ _setup_browser_book() -> Create and setup the tabs for browsers 
        
        """

        # Connection dictionary for the browser tabs
        connection_dict = {
                'title-changed' : self._browser_book_title_changed,
                'tab-closed' : self._browser_book_browser_closed,
                'tab-added' : self._browser_book_browser_added,
                'new-tab' : self._browser_book_new_tab,
                'duplicate-tab' : self._browser_book_duplicate_tab,
                'exit' : self._browser_book_exit,
                'paste-tab' : self._browser_book_paste_tab,
                'notify::current-page' : self._browser_book_page_changed,
                'create-window' : self._browser_book_create_window,
                'drag-begin' : self._browser_book_drag_begin,
                }

        # Connect signals to callback functions
        for signal, callback in connection_dict.iteritems():
            self._browser_book.connect(signal, callback)

    def _setup_bookmark_menu(self):
        """ _setup_bookmark_menu() -> Connect the bookmark menu signals to
        callback functions to handle them. 
        
        """

        # Connection dictionary
        bookmark_menu_connect_dict = {
            'bookmark-button-release' : self._bookmark_clicked,
            'new-bookmark' : self._bookmark_new,
            'bookmark-tabs' : self._bookmark_tabs,
            'folder-as-tabs' : self._bookmark_open_folder,
            }

        # Connect signals to callback functions
        for signal, callback in bookmark_menu_connect_dict.iteritems():
            self._bookmark_menu.connect(signal, callback)

    def _setup_accels(self):
        """ _setup_accels() -> Setup the keyboard shortcuts. 
        
        """

        # Dictionary of keyboard shortcuts and callback functions
        accel_dict = {
                ('<Control>c',): self._copy_text_key_pressed,
                ('<Control>m',): self._minimize_tab_key_pressed,
                ('<Control>t', '<Control><Shift>t'): self._new_tab_key_pressed,
                ('<Control>w',): self._close_tab_key_pressed,
                ('<Control><Shift>w',): self._close_all_tabs_key_pressed,
                ('<Control><Alt>w',): self._close_other_tabs_key_pressed,
                ('<Control>l',): self._focus_address_entry_key_pressed,
                ('<Control>k',): self._focus_search_entry_key_pressed,
                ('<Control>f',): self._toggle_findbar_key_pressed,
                ('<Control>r', '<Control><Shift>r', 'F5'): \
                        self._refresh_page_key_pressed,
                ('<Control>g',): self._find_next_key_pressed,
                ('Escape',): self._escape_key_pressed,
                ('<Control>d',): self._new_bookmark_key_pressed,
                ('<Control>h',): self._hide_tab_title_key_pressed,
                ('<Control>plus',): self._zoom_in_key_pressed,
                ('<Control>minus',): self._zoom_out_key_pressed,
                ('<Control><Shift>h',): self._hide_tab_bar_key_pressed,
                ('<Control><Shift><Alt>h',): self._hide_term_bar_key_pressed,
                ('<Control><Shift>b',): self._focus_view_key_pressed,
                ('<Alt>b',): self._go_back_key_pressed,
                ('<Alt>f',): self._go_forward_key_pressed,
                ('<Control>q',): self._quit_key_pressed,
                }

        # Connect signals to signal handlers
        for accel_tuple, handler_func in accel_dict.iteritems():
            for accel in accel_tuple:
                keyval, modifier = gtk.accelerator_parse(accel)
                self._accels.connect_group(keyval, modifier, 
                        gtk.ACCEL_VISIBLE, handler_func)

        # Setup keyboard shortcuts for switching tabs
        for i in xrange(9):
            self._accels.connect_group(gtk.gdk.keyval_from_name(str(i)),
                    gtk.gdk.MOD1_MASK, gtk.ACCEL_VISIBLE, 
                    self._switch_tab_key_pressed)

    def run(self, addtab=True):
        """ run(addtab=True) -> Show the main window and setup stuff before 
        calling gtk.main to run the browser. 
        
        """

        # Redirect warnings to debug terminal.
        with redirect_warnings(self._showwarning):
            # redirect stdout to debug terminal
            #with StdoutRedirect(self.print_message, MSGCOLOR, '38;5;96') as \
                    #new_stdout:

            self._window.show_all()

            # Set debug terminal to default visibility
            self._term_book.set_property('visible', False)

            # Start file watcher.
            if self._file_watcher:
                self._file_watcher.start()

            # Load plugins.
            self._plugins.load_list('%s/plugins' % self._path, 'main')

            # Restore tabs from tab restore file.
            self._tab_manager.import_list(self._tabs_file)

            if addtab:
                # Open a new tab if no tabs are open.
                if self._browser_book.get_n_pages() == 0:
                    def new_tab():
                        self.do_open_tab()
                    glib.idle_add(new_tab)

            # Add a timeout to periodically save the open tabs.
            self._save_event = glib.timeout_add_seconds(30, 
                    self._browser_book.save_tabs)

            BrowserBase.window_set.add(self)

            if len(BrowserBase.window_set) == 1:
                gobject.threads_init()
                gtk.main()

    def exit(self, window):
        """ exit(window) -> Called to exit the browser.  Cleans up
        implementation independent parts of the browser. 
        
        """

        # Stop the save event.
        if self._save_event:
            glib.source_remove(self._save_event)

        # Unload the plugins.
        self._plugins.unload()

        # Stop file watcher.
        if self._file_watcher:
            if self._file_watcher.is_running():
                self._file_watcher.stop()

        # Clean up the download manager
        self._download_manager.stop_all()

        # Save the tabs.
        self._browser_book.save_tabs()

        # Close all tabs
        self._browser_book.disconnect_by_func(
                self._browser_book_browser_closed
                )
        for browsebox in self._browser_book.get_children():
            self._browser_book.close_tab(browsebox)

        # Run inheritor exit function
        self.do_exit()

        try:
            BrowserBase.window_set.remove(self)
        except KeyError:
            pass

        if len(BrowserBase.window_set) == 0:
            # Quit the main loop
            gtk.main_quit()

    def do_exit(self):
        """ do_exit() -> To be implemented by inheritor. 
        
        """

        pass

    def _showwarning(self, message, category, filename, lineno, file=None, 
            line=None):
        """ _showwarning(message, category, filename, lineno, file=None, 
                line=None) -> 
        Override the default showwarning function to redirect warning output to
        the debug terminal. 
        
        """

        warning_str = 'main: warning: %s (%s): %s' % \
                (os.path.basename(filename), lineno, message)
        self.print_message(warning_str, MSGCOLOR, '38;5;96')

    def stdout_print_message(self, message, color=0, data_color=''):
        """ stdout_print_message(message, color=0, data_color='') -> Print
        message to stdout.  The 'color' argument specifies the desired color
        for the message name, and the 'data_color' argument specifies the
        color to be used for the message type.

        """

        # Return false when an empty message is given.
        if not message.strip():
            return False
        
        # Print the date and time at the start of the output.
        # Format: Month Day Hour:Minute:Second
        date = strftime('%h %e %H:%M:%S')

        # Colorize the output if colors are given in the 'color' and 
        # 'data_color' arguments.
        if color != 0:
            if data_color == '':
                message_list = message.split(':', 1)
                messagestr = "[38;5;75m%s [0;%sm%s[m:%s" % (date, color, 
                        message_list[0], ''.join(message_list[1:]))
            else:
                message_list = message.split(':', 2)
                if len(message_list) > 2:
                    messagestr = "[38;5;75m%s [0;%sm%s[m:[%sm%s[m:%s" % \
                            (date, color, message_list[0], data_color, 
                                    message_list[1], ''.join(message_list[2:]))
                else:
                    message_list = message.split(':', 1)
                    messagestr = "[38;5;75m%s [0;%sm%s[m:%s" % (date, 
                            color, message_list[0], ''.join(message_list[1:]))
        else:
            messagestr = "[38;5;75m%s[m %s" % (date, message)

        self._stdout.write('%s\n' % messagestr)
        self._stdout.flush()

    def _print_message_handler(self, browsebox, *args):
        """ Handle browsebox print message signals.

        """

        self.print_message(*args)

    def print_message(self, message, color=0, data_color=''): 
        """ print_message(message, color=0, data_color='') -> Print messages
        to the debug terminal. 
        
        """

        if not self.emit('message', message, color, data_color):
            # Print the message to 'stdout' if no one handled the signal.
            self.stdout_print_message(message, color, data_color)

        # Log the message to a file.
        #with open('browser-%d.log' % os.getpid(), 'a') as log_file:
            #log_file.write(message)
            #log_file.flush()

    def do_receive_embed_mime_uri(self, mimetype, uri, handler_cmd_str):
        """ do_receive_embed_mime_uri(embedmimetype, uri) -> Handle received 
        mimetypes and uris 
        
        """

        if sys.modules.has_key('wnck'):
            # Get a temp file name to hold the downloaded file.
            temp_file = '/tmp/%s' % tempfile._get_candidate_names().next()

            # Exit if no handler was given.
            if not handler_cmd_str:
                return False

            embed_app = EmbedApp()

            connect_dict = {
                    'plug-removed': (self._embed_removed, temp_file),
                    'closing': (self._embed_closing, temp_file),
                    }

            # Connect the signals to signal-handlers.
            for signal, args in connect_dict.iteritems():
                if type(args) == tuple:
                    embed_app.connect(signal, *args)
                else:
                    embed_app.connect(signal, args)

            embed_app.show_all()

            self._browser_book.new_tab(embed_app)

            # Make the command list from handler_cmd_str.
            if handler_cmd_str.find('%d') != -1:
                cmd_str = handler_cmd_str % (embed_app.get_id(), temp_file)
            else:
                cmd_str = handler_cmd_str % temp_file
            handler_cmd = cmd_str.split()

            # Start a thread to download and embed.
            download_thread = threading.Thread(
                    target=self._embed_download_file, 
                    args=(uri, temp_file, embed_app, handler_cmd))

            # Make the thread a daemon so it won't stop the main program 
            # from exiting
            download_thread.daemon = True
            try:
                download_thread.start()
            except:
                pass

    def _embed_download_file(self, uri, temp_file, embed_app, handler_cmd):
        """ _embed_download_file(uri, temp_file, embed_app, handler_cmd) ->
        Download 'uri' to 'temp_file' and when finished embed 'handler_cmd'
        in 'embed_app.'

        """

        try:
            grabber = urllib.FancyURLopener()
            grabber.retrieve(uri, temp_file)

            embed_app.run(handler_cmd)
        except Exception as err:
            self.print_message(
                    'main: There as an exception (%s) while downloading: %s' \
                            % (err, uri), MSGCOLOR)

    def do_receive_download_uri(self, filename, uri):
        """ do_receive_download_uri(filename, uri) -> Handle received
        download uris 
        
        """

        if self._download_manager.add_download(uri, filename):
            #self._term_book.toggle_visible(self._download_manager, True)
            self.print_message("received download uri: %s" % uri, MSGCOLOR)

    def do_open_tab(self, flags=0, tab=None, uri=None, popup=False, 
            pid=None, history_str='', history_index=1, button=None):
        """ do_open_tab(flags=0, tab=None, uri=None, popup=False, 
        pid=None, history_str='', history_index=1) -> Open a new tab based on
        the arguments given.  To be implemented by inheritor. 
        
        """

        pass

    def _record_closed_tab(self, browsebox):
        """ _record_closed_tab(browsebox) -> Save the information about the
        tab 'browsebox' so it can be reopened.

        """

        info_list = self._browser_book.get_tab_info(browsebox)
        # Ignore blank tabs.
        if info_list:
            self._tab_manager.add_tab(browsebox.get_icon().get_default_icon(),
                    info_list, self._browser_book.page_num(browsebox))

    def _reopen_tab(self, tab_manager, tab_dict, flags):
        """ _reopen_tab(tab_manager, tab_dict, flags) -> Reopen a closed tab
        based on the information in tab_dict.

        """

        glib.idle_add(self.do_restore_tab, tab_dict, flags)

    def do_restore_tab(self, tab_dict):
        """ do_restore_tab(tab_dict) -> Restores a tab based on 'tab_dict'.
        Should be implemented by 
        inheritor.

        """

        pass

    def _bookmark_open_folder(self, bookmark_menu, event, folder, bookmarks):
        """ _bookmark_open_folder(bookmark_menu, event, folder, bookmarks) ->
        Opens all the bookmarks in 'folder' as new tabs.  If shift is held down
        then all the back history of the current tab should be copied to each
        new tab. 
        
        """

        def open_tab(flags, tab, uri):
            """ open_tab(flags, tab, uri) -> A local function to open a tab.

            """

            self.do_open_tab(flags=flags, tab=tab, uri=uri)
            return False

        for bookmark in bookmarks.get_bookmark_list_sorted(folder, 
                reverse=True):
            uri = bookmarks.get_uri(bookmark)
            glib.idle_add(open_tab, event.state, self._current_tab, uri)

    def _bookmark_tabs(self, bookmark_menu, folder, bookmarks):
        """ _bookmark_tabs(bookmark_menu, folder, bookmarks) -> Bookmark
        all the tabs as a folder. 
        
        """

        for tab in self._browser_book:
            bookmarks.add_bookmark(tab.get_title(), tab.get_uri(), folder)

    def _bookmark_new(self, bookmark_menu):
        """ _bookmark_new(bookmark_menu) -> Give the bookmark menu the
        current tab title and uri. 
        
        """

        return self._current_tab.get_title(), self._current_tab.get_uri()

    def _bookmark_clicked(self, bookmark_menu, event, uri):
        """ _bookmark_clicked(bookmark_menu, event, uri) -> Open bookmark.
        If it is middle clicked then the bookmark will be opened in a new
        tab.  If shift is held down then all the back history of the current
        tab should be copied to the new tab. 
        
        """

        if event.button == 2:
            self.do_open_tab(event.state, uri=uri)
        else:
            self._current_tab.load_uri(uri)

    def _browser_book_drag_begin(self, browser_book, context):
        """ Disconnect the current tab when a drag begins.
        The current tab will be the dragged tab.

        """

        self.do_connect_tab(self._current_tab, disconnect=True)

    def _browser_book_create_window(self, browser_book, browsebox, x, y):
        """ Creates a new window for the dragged tab.

        """

        window = self.do_create_window(browsebox=browsebox)
        if window:
            #self.do_connect_tab(self._current_tab, disconnect=True)
            #self._browser_book.close_tab(browsebox)
            #window.do_connect_tab(browsebox)
            window._window.move(x, y)
            window.run(addtab=False)
            #window.do_open_tab(tab=browsebox, history_str=browsebox.get_history_str())
            return window._browser_book

    def _browser_book_page_changed(self, browser_book, property):
        """ _browser_book_page_changed(browser_book, property) -> Called when
        the current tab is changed. 
        
        """

        self._current_tab = browser_book.get_property(property.name)

    def _browser_book_paste_tab(self, browser_book, tab, flags):
        """ _browser_book.paste_tab(browser_book, tab, flags) -> Paste the 
        clipboard into a new tab after 'tab.'

        """

        clipboard = gtk.clipboard_get('CLIPBOARD')
        tab_str = clipboard.wait_for_text()
        try:
            index = self._browser_book.page_num(tab) + 1
            #for info_str in tab_str.split('\n'): 
            for info_list in json.loads(tab_str):
                #info_list = json.loads(info_str)
                glib.idle_add(self.do_restore_tab, 
                        {'info_list':info_list, 'index':index}, flags)
                index += 1
        except:
            pass

    def _browser_book_title_changed(self, browser_book, title):
        """ _browser_book_title_changed(browser_book, title) -> Called when
        the current tabs title changes. 
        
        """

        self._window.set_title('%s - Browser' % title)

    def _browser_book_exit(self, browser_book):
        """ _browser_book_exit(browser_book) -> Called when all the tabs
        have been closed so the window should be as well.

        """

        self._window.destroy()

    def _browser_book_browser_added(self, browser_book, browsebox):
        """ _browser_book_browser_added(browser_book browsebox) -> Connect
        and finish setting up the tab.

        """

        self.do_connect_tab(browsebox)

    def _browser_book_browser_closed(self, browser_book, browsebox):
        """ _browser_book_browser_closed(browser_book browsebox) -> A cleanup
        function to cleanup after a tab is closed.

        """

        # Save tabs for crash recovery.
        self._browser_book.save_tabs(exclude=(browsebox,))
        
        self._record_closed_tab(browsebox)

        if self._current_tab == browsebox:
            # Remove reference to the closed tab.
            self._current_tab = None

        self.do_browser_closed(browsebox)

    def _browser_book_duplicate_tab(self, browser_book, flags, tab):
        """ _browser_book_duplicate_tab(browser_book, event, tab) -> Duplicate
        'tab'.  If shift is held down then all history should be duplicated as 
        well. 
        
        """

        uri = tab.get_uri()
        self.do_open_tab(flags=flags, uri=uri, tab=tab, 
                history_index=tab.get_history_index())

    def _browser_book_new_tab(self, browser_book, flags, tab):
        """ _browser_book_new_tab(browser_book, event) -> Opens a new tab if
        shift is held down then all back history should be copied to the new 
        tab. 
        
        """

        self.do_open_tab(flags=flags, tab=tab)

    def _browser_popup_bookmark_menu(self, browsebox, event):
        """ _browser_popup_bookmark_menu(browsebox, event) -> Pop up the
        bookmark menu based on event. 
        
        """

        self._bookmark_menu.popup_menu(event)

    def _browser_new_tab(self, browsebox, arg_dict):
        """ _browser_new_tab(browsebox, arg_dict) -> Creates a new tab
        based on the values in arg_dict dictionary.  Returns the value
        of the inheritor's new_tab function.
        
        """

        return self.do_open_tab(tab=browsebox, **arg_dict)

    def _browser_embed_mime_uri(self, browsebox, mimetype, uri, handler_str):
        """ _browser_embed_mime_uri(browsebox, mimetype, uri) -> Handle a 
        mimetype that the browser can't view.

        """

        self.do_receive_embed_mime_uri(mimetype, uri, handler_str)

    def _browser_download_uri(self, browsebox, filename, uri):
        """ _browser_download_uri(browsebox, filename, uri) -> Add uri
        to download manager, using filename as the default filename.

        """

        self.do_receive_download_uri(filename, uri)

    def new_tab(self, **kwargs):
        """ new_tab(**kwargs) -> To be implemented by inheritor. 
        
        """

        pass

    def do_create_window(self, browsebox):
        """ Create a new window.

        """

        pass

    def do_new_tab(self, browsebox, uri=None, popup=False):
        """ do_new_tab(browsebox, uri=None, popup=False) -> Connect default 
        signals and add new tab to the browser tab book.

        """

        #browsebox.set_address_completion(self._completion_model)

        # The new tab should be switched to if uri is set or popup is True
        switch_new_tab = (uri == None and popup == False)
        self._browser_book.new_tab(browsebox, switch_new_tab) 

    def _toggle_visible(self, browsebox, child):
        """ Handle browsebox toggle buttons.

        """

        self._term_book.toggle_visible(child)

    def _skip_embed_app(func):
        """ Skip any wrapped function if the tab it is operating on is an
        embeded app tab.

        """

        def wrap_func(self, *args):
            try:
                if not isinstance(self._current_tab, EmbedApp):
                    return func(self, *args)
            except Exception as err:
                print("Error %s" % err)
                return None

        return wrap_func

    @_skip_embed_app
    def do_connect_tab(self, browsebox, disconnect=False):
        """do_connect_tab(browsebox, disconnect=False) -> Connect signal 
        handlers to the tab.  If disconnect is True than disconnect instead 
        of connect.

        """

        connection_dict = {
                'browser-new-tab': (self._browser_new_tab,),
                'download-uri' : (self._browser_download_uri,),
                'embed-mime-uri' : (self._browser_embed_mime_uri,),
                'popup-bookmark-menu': (self._browser_popup_bookmark_menu,),
                'print-message': (self._print_message_handler,),
                'toggle-download-manager' : (self._toggle_visible,
                            self._download_manager),
                'toggle-tab-manager': (self._toggle_visible,
                        self._tab_manager),
                'hover-uri': (self._update_status,),
                }
        for signal, callback in connection_dict.iteritems():
            if disconnect:
                try:
                    browsebox.disconnect_by_func(callback[0])
                except TypeError:
                    pass
            else:
                browsebox.connect(signal, *callback)

    def _update_status(self, browsebox, uri):
        """ _update_status(browsebox, uri) -> handles hover uris when they 
        are received (i.e. putting them in the status bar)
        
        """

        if uri != "None":
            self._status_bar.pop(1)
            self._status_bar.push(1, uri)
        else:
            self._status_bar.pop(1)

    def do_browser_closed(self, browsebox):
        """ do_browser_closed(browsebox) -> Clean up after a tab is closed.
        To be implemented by inheritor. 

        """

        pass

    def _copy_text_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _copy_text_key_pressed() -> Copy text when copy keyboard shortcut
        is pressed. 
        
        """

        selection = gtk.clipboard_get(selection='PRIMARY').wait_for_text()
        if selection:
            clipboard = gtk.clipboard_get(selection='CLIPBOARD')
            clipboard.set_text(selection)
            clipboard.store()

    def _new_tab_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _new_tab_key_pressed() -> Opens a new tab if shift is held down 
        then all back history should be copied to the new tab. 
        
        """

        self.do_open_tab(flags)

    @_skip_embed_app
    def _print_page_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _print_page_key_pressed() -> Tell the current tab to print the 
        page. 
        
        """

        self._current_tab.print_page()

    @_skip_embed_app
    def _go_back_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _go_backt_key_pressed() -> Tell the current tab to go back
        
        """

        self._current_tab.do_go_back()

    @_skip_embed_app
    def _go_forward_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _go_forward_key_pressed() -> Tell the current tab to go forward
        
        """

        self._current_tab.do_go_forward()

    def _quit_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _quit_key_pressed() -> Tell the browser to quit.
        
        """

        self.exit(self._window)

    def _new_bookmark_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _new_bookmark_key_pressed() -> Bookmark the current tab. 
        
        """

        self._bookmark_menu.new_bookmark(self._current_tab.get_title(), 
                self._current_tab.get_uri())

    @_skip_embed_app
    def _focus_address_entry_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _focus_address_entry_key_pressed() -> Give input focus to the 
        current tabs address entry 
        
        """

        self._current_tab.focus_address_entry()
        return True

    @_skip_embed_app
    def _focus_search_entry_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _focus_search_entry_key_pressed() -> Give input focus to the 
        current tabs search entry. 
        
        """

        self._current_tab.focus_search_entry()
        return True

    @_skip_embed_app
    def _toggle_findbar_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _toggle_findbar_key_pressed() -> Toggle the visibility of the 
        current tabs find tool bar. 
        
        """

        self._current_tab.toggle_findbar()
        return True

    @_skip_embed_app
    def _zoom_in_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _zoom_in_key_pressed() -> Zoom in the webpage.        

        """

        self._current_tab.zoom(1)

    @_skip_embed_app
    def _zoom_out_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _zoom_out_key_pressed() -> Zoom out the webpage.        

        """

        self._current_tab.zoom(0)

    @_skip_embed_app
    def _escape_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _escape_key_pressed() -> Stop the current page from loading
        if it is loading otherwise hide the current tabs find bar if
        it is visible. 
        
        """

        if self._current_tab.is_loading():
            self._current_tab.stop_loading()
        elif self._current_tab.findbar_visible():
            self._current_tab.toggle_findbar(True)

    @_skip_embed_app
    def _refresh_page_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _refresh_page_key_pressed() -> Refresh the current page. 
        
        """

        if not self._current_tab.is_loading():
            self._current_tab.refresh_page()

    def _focus_view_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _focus_view_key_pressed() -> Set focus to the browser view. 
        
        """

        self._current_tab.take_focus()
 
    def _hide_term_bar_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _hide_term_bar_key_pressed() -> Toggle the visibility of the 
        terminal and download tabs. 
        
        """

        self._term_book.set_show_tabs(not 
                self._term_book.get_show_tabs())

    def _hide_tab_bar_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _hide_tab_bar_key_pressed() -> Toggle the visibility of the 
        browser tabs. 
        
        """

        self._browser_book.set_show_tabs(not 
                self._browser_book.get_show_tabs())

    def _hide_tab_title_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _hide_tab_title_key_pressed() -> Toggle the visibility of the 
        current tabs title and icon. 
        
        """

        self._browser_book.toggle_hide_tab()

    def _minimize_tab_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _minimize_tab_key_pressed() -> Hide the current tabs title. 
        
        """

        self._browser_book.toggle_minimize_tab()

    @_skip_embed_app
    def _find_next_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _find_next_key_pressed() -> Find the next occurrence in the current
        tabs browser. 
        
        """

        self._current_tab.find_on_page()

    def _close_tab_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _close_tab_key_pressed() -> Close the current tab. 
        
        """

        self._browser_book.close_tab()

    def _close_all_tabs_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _close_all_tabs_key_pressed() -> Close all the tabs, and open a 
        blank one.
        
        """

        current_tab = self._current_tab
        for tab in self._browser_book.get_children():
            if tab != current_tab:
                self._browser_book.close_tab(tab)
        self.do_open_tab()
        self._browser_book.close_tab(current_tab)

    def _close_other_tabs_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _close_other_tabs_key_pressed() -> Close all the tabs except the 
        current one. 
        
        """

        current_tab = self._current_tab
        for tab in self._browser_book.get_children():
            if tab != current_tab:
                self._browser_book.close_tab(tab)

    def _switch_tab_key_pressed(self, accels=None, window=None, keyval=None, 
            flags=None):
        """ _switch_tab_key_pressed() -> Change tabs based on the number. 
        
        """

        if keyval:
            index = int(gtk.gdk.keyval_name(keyval)) - 1
            self._browser_book.set_current_page(index)

    # Functions for the embed window thing
    def _embed_file_downloaded(self, file_grabber, filename, embed_app, 
            handler_cmd):
        """ _embed_file_downloaded(file_grabber, filename, embed_app, 
        handler_cmd) -> Called when the file to be embeded is finished 
        downloading.  Starts the embeded application.

        """

        embed_app.run(handler_cmd)

    def _embed_removed(self, embed_app, temp_file):
        """ _embed_removed(embed_app, temp_file) -> Called when the embeded
        application exits.  Some cleanup stuff is done here such as removing
        the temporary file.

        """

        if os.path.isfile(temp_file):
            os.unlink(temp_file)

        self._browser_book.close_tab(embed_app)

    def _embed_closing(self, embed_app, temp_file):
        """ _embed_closing(embed_app, temp_file) -> Called when the tab
        holding the embeded app is closing.  Do some cleanup such as
        removing the temporary file.

        """

        if os.path.isfile(temp_file):
            os.unlink(temp_file)

class ProfileManager(dbus.service.Object):
    """ Manage the running and stopping of a browser in a given profile.

    """

    def __init__(self, bus, options_dict, uri_callback):
        """ ProfileManager(bus, options_dict, uri_callback) -> An 
        object used to start and control a browser.

        """

        profile = options_dict.get('profile', 'default')
        uri = options_dict.get('uri', '')

        # Make sure the profile directory exists before doing anything.
        config_dir = glib.get_user_config_dir()
        app_dir = '%s/%s' % (config_dir, APP_NAME)
        profile_dir = '%s/%s' % (app_dir, profile)

        if not os.path.isdir(profile_dir):
            for path in [config_dir, app_dir, profile_dir]:
                if not os.path.isdir(path):
                    os.mkdir(path)

        # This is the profiles pid file.
        pid_file = '%s/%s.pid' % (app_dir, profile)

        if not self.first(pid_file):
            # A browser in this profile is already running, so just send it 
            # the given uri to load.
            bus.get_object('com.browser.main', '/%s' % profile).load_uri(uri)
            self._pid_file = None
        else:
            # This is the only browser in this profile.
            super(ProfileManager, self).__init__(bus, '/%s' % profile)

            self._bus = bus
            self._load_uri = uri_callback
            self._pid_file = pid_file

    def first(self, filename):
        """ first(filename) -> If the file exists return False if the 
        pid owner is still running, otherwise return True.

        """

        if not os.path.isfile(filename):
            # No file so no browser in this profile is running.
            return True

        with open(filename, 'r') as pid_file:
            pid = int(pid_file.read())

        try:
            # If the pid is still in use this will not raise an exception.
            os.kill(pid, 0)
            return False
        except OSError:
            # This pid in the file is not in use, so remove the file.
            os.unlink(filename)
            return True

    @dbus.service.method(dbus_interface='com.browser.main', in_signature='s')
    def load_uri(self, uri):
        """ load_uri(uri) -> Tell the main browser to load the given uri.

        """

        self._load_uri(uri)

    def __enter__(self):
        """ Write the pid file and start the browser.

        """

        try:
            if self._pid_file:
                # If the pid file variable is not set then this is just run 
                # to open a new tab to an already running window, so do 
                # nothing.

                # Write the pid to the pid file.
                with open(self._pid_file, 'w') as pid_file:
                    pid_file.write(str(os.getpid()))

            return self
        except Exception as err:
            print(err)
            return None

    def __exit__(self, exc_type, exc_value, traceback):
        """ When finished remove the pid file, and if there were any 
        exceptions return False to indicate that they were not handled.

        """

        try:
            if self._pid_file:
                # A pid file was created so remove it when we exit.
                os.unlink(self._pid_file)

            if exc_type:
                return False
            return True
        except Exception as err:
            print(err)
            return False
