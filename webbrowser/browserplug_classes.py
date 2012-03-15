# This file is part of browser, and contains the base class for the browser 
# view object.
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

""" A gtk HPaned with a webkit WebView added to a ScrolledWindow.  

This module should be used as either a base or added to a main browser 
window or tab.

"""

import os
import sys
import subprocess
import re
import tempfile
import json
import re
import threading
from os.path import isfile as os_isfile

import gtk
import webkit
import glib
import gobject
import pango
import urllib2

from classes import SearchMenu, SaveDialog, Config
from file_watch import FileWatcher
from plugin_loader import Plugins
from functions import extern_load_uri
from defaults import APP_NAME

# Set the default tab message color.
MSGCOLOR = 32

class BrowserView(gtk.HPaned):
    """ BrowserView -> Provides a browser window, either to embed in a socket
    and control over dbus, or to just add to a window as any other widget.

    """

    # Define the gobject signals that BrowserView can emit.
    __gsignals__ = {
            'new-browser' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_PYOBJECT, 
                ()),
            'new-tab' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING, gobject.TYPE_LONG)),
            'title-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING,)),
            'back-forward' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN)),
            'download-uri' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING, gobject.TYPE_STRING)),
            'embed-mime-uri' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING, gobject.TYPE_STRING, 
                    gobject.TYPE_STRING)),
            'uri-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING,)),
            'hover-uri' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING,)),
            'favicon-uri' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING,)),
            'progress-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_FLOAT,)),
            'show-hide-download' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, 
                ()),
            'message' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING, gobject.TYPE_UINT, gobject.TYPE_STRING)),
            'populate-popup' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (gobject.TYPE_PYOBJECT,)),
            'resource-request' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_STRING, (gobject.TYPE_STRING,)),
            'plugin-request' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, (gobject.TYPE_STRING,)),
            'load-status' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (gobject.TYPE_INT, )),
            }

    def __init__(self, profile='default'):
        """ BrowserView(profile='default') -> Provides a way to add and 
        control a webkit browser object to a window or (if inherited) a gtk 
        socket.

        """

        super(BrowserView, self).__init__()


        # We need to setup the proxy before we create the browser object.
        try:
            # Get the proxy url from the 'http_proxy' environment variable.
            proxy = os.getenv('http_proxy')
            if not proxy:
                raise(Exception, "$http_proxy not set")
            import ctypes
            from ctypes.util import find_library
            libgobject = ctypes.cdll.LoadLibrary(find_library('gobject-2.0'))
            libsoup = ctypes.cdll.LoadLibrary(find_library('soup-2.4'))
            libwebkit = ctypes.cdll.LoadLibrary(find_library('webkitgtk-1.0'))
            proxy_uri = libsoup.soup_uri_new(proxy)
            session = libwebkit.webkit_get_default_session()
            libgobject.g_object_set(session, "proxy-uri", proxy_uri, None)
            #from gi.repository import Soup as libsoup
            #from gi.repository import WebKit as libwebkit
            #proxy_uri = libsoup.URI.new(proxy)
            #session = libwebkit.get_default_session()
            #session.set_property('proxy-uri', proxy_uri)
        except Exception as err:
            # If it fails than we just won't use a proxy.
            self.print_message("Failed to set a proxy: %s" % err,
                               MSGCOLOR, '38;5;64')

        self._profile = profile

        # _key_flags is used to check what keys where pressed when a link 
        # was clicked.
        self._key_flags = None

        self._path = os.path.dirname(__file__)
        self._config_path = '%s/%s/%s' % (glib.get_user_config_dir(), 
                APP_NAME, self._profile)

        SearchMenu._profile_path = self._config_path

        self._browser = webkit.WebView()
        self.connect('grab-focus', lambda *a: self._browser.grab_focus())

        # Setup a configuration.
        self._config = Config('%s/browser_tab.conf' % self._config_path)
        self._setup_config()

        # Add a file watcher.
        if FileWatcher.check():
            self._file_watcher = FileWatcher()
            self._file_watcher.add_directory(self._config_path)
            self._file_watcher.add_directory('%s/%s' % (glib.get_user_config_dir(), 
                APP_NAME))
            self._file_watcher.start()
        else:
            self._file_watcher = None

        # Load the tab plugins first.
        self._plugins = Plugins(self, self._profile)
        self._plugins.load_list('%s/plugins' % self._path, 'tab')

        # Setup browser an connect signal handlers.
        self._setup_browser()

        self._scrolled_window = gtk.ScrolledWindow()
        self._scrolled_window.set_policy('automatic', 'automatic')
        self._scrolled_window.set_shadow_type(gtk.SHADOW_IN)

        self._scrolled_window.add(self._browser)

        self.add1(self._scrolled_window)
        self.set_property('position_set', True)

        # Setup the search engine menu.
        self._search_engine_menu = SearchMenu()
        self._search_engine_menu.build_menu()

        self._search_menu_item = self._make_menu_item('search', 
                'Search _Using...', 'Search Using...', None)
        self._search_menu_item.set_use_underline(True)
        self._search_menu_item.set_submenu(self._search_engine_menu)
        self._search_engine_menu.connect('engine-clicked', self._search_web, 
                self._search_menu_item)

        # The settings menu.
        self._settings_menu = gtk.Menu()
        self._plugins_menu = gtk.Menu()

        self._current_folder = os.getenv('HOME')

        # The current uri that the mouse is over is held in this variable.
        self._hover_uri = ''

        # A list to store the temporary files, so they can be closed when the
        # tab is closed.
        self._temp_files = []

        # Get pdf mime handler.
        self._mime_handler_dict = self._build_mime_handlers()

        self._web_inspector = None

    def _build_mime_handlers(self):
        """ _build_mime_handlers() -> Build and return a dictionary of mime
        types and the applications to handle them.

        """

        handler_dict = {}

        # A list of mime types to handle.
        mime_types = ['application/pdf']

        for mime in mime_types:
            try:
                handler_desktop = subprocess.Popen(
                        ['xdg-mime', 'query', 'default', mime], 
                        stdout=subprocess.PIPE).communicate()[0].strip()
            except Exception as err:
                print("Error in subprocess build_mime_handlers: %s" % err)
                break

            if not handler_desktop:
                continue
            try:
                with open('/usr/share/applications/%s' % handler_desktop, 'r') as desktop_file:
                    for line in desktop_file.readlines():
                        if line.lower().startswith('exec'):
                            handler = '%s %%s' % line.split('=')[-1].split()[0]
                            break
            except Exception as err:
                continue

            if handler:
                handler_dict[mime] = handler

        # A dictionary of mime-types and the command string to open them.
        #handler_dict = {
                #'application/pdf': handler,
                #'application/pdf': 'xdg-open %s',
                #'application/vnd.oasis.opendocument.formula' : '/usr/lib/openoffice/program/soffice.bin %s',
                #}

        return handler_dict

    def _setup_browser(self, disconnect=False):
        """ _setup_browser(disconnect=False) -> Connect the browser callbacks
        if disconnect is False.

        """

        browser_connection_dict = { 
                'hovering-over-link':self._browser_hovering_over_link,
                'populate-popup':self._browser_popup,
                'new-window-policy-decision-requested': \
                        self._browser_new_window,
                'create-web-view':self._browser_new_webview,
                'console-message':self._browser_console_message,
                'download-requested':self._browser_download_requested,
                'create-plugin-widget':self._browser_create_plugin,
                'navigation-policy-decision-requested': \
                        self._browser_nav_policy_request,
                'mime-type-policy-decision-requested': \
                        self._browser_mime_decision_requested,
                'resource-request-starting': \
                        self._browser_resource_request_starting,
                'icon-loaded':self._browser_icon_loaded,
                'print-requested':self._browser_print,
                'key-press-event':self._browser_key_press,
                'button-press-event':self._browser_button_press_event,
                'scroll-event':self._browser_scroll_event,
                'notify::uri':self._browser_uri_changed,
                'notify::title':self._browser_title_changed,
                #'notify::load-status':self._browser_load_status_changed,
                'notify::progress':self._browser_progress_changed,
                'notify':self._browser_property_changed,
                #'web-view-ready':self._browser_view_ready,
                }

        for signal, callback in browser_connection_dict.iteritems():
            if not disconnect:
                self._browser.connect(signal, callback)
            else:
                try:
                    self._browser.disconnect_by_func(callback)
                except TypeError:
                    pass

    def _make_menu_item(self, icon_name, label_text, tooltip_text, 
            click_func, *user_args):
        """ _make_menu_item(icon_name, label_text, tootip_text, click_func, 
        *user_args) -> Create a menu item based on the function arguments.

        """

        icon = gtk.Image()
        icon.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)
        menu_item = gtk.ImageMenuItem()
        menu_item.set_image(icon)
        menu_item.set_label(label_text)
        menu_item.set_tooltip_text(tooltip_text)
        menu_item.set_use_underline(True)
        if click_func:
            menu_item.connect('button-release-event', click_func, *user_args)

        return menu_item

    def _plugins_item(self):
        """ _plugins_item -> Creates a menu to enable/disable plugins.

        """

        def toggle_plugin(toggle_item, plugin_name):
            if toggle_item.get_active():
                self._plugins.enable(plugin_name)
            else:
                self._plugins.disable(plugin_name)

        self._plugins_menu = gtk.Menu()

        menu_item = gtk.ImageMenuItem(gtk.STOCK_REFRESH) 
        menu_item.connect('activate', lambda *a: self._plugins.load_list('%s/plugins' % self._path, 'tab'))
        self._plugins_menu.add(menu_item)
 

        for name, active in self._plugins.get_iter():
            title = name.split('_')
            title = ' '.join(title[1:])
            menu_item = gtk.CheckMenuItem(title.capitalize())
            menu_item.set_active(active)
            menu_item.connect('toggled', toggle_plugin, name)
            self._plugins_menu.add(menu_item)

        self._plugins_menu.show_all()

        plugins_item = self._make_menu_item('gtk-preferences', 
                'Configure _Plugins', 'Configure Tab Plugins', None)
        plugins_item.set_submenu(self._plugins_menu)
        plugins_item.show_all()

        return plugins_item

    def _settings_item(self):
        """ _settings_item() -> Creates the settings menu.

        """

        self._settings_menu = gtk.Menu()

        menu_item_tup = (
                ('Auto _Load Images', True, 
                    self.get_browser_setting('auto-load-images'), 
                    (self._toggle_setting, 'auto-load-images')),
                ('Auto _Shrink Images', True, 
                    self.get_browser_setting('auto-shrink-images'), 
                    (self._toggle_setting, 'auto-shrink-images')),
                ('Enable _Plugins', True, 
                    self.get_browser_setting('enable-plugins'), 
                    (self._toggle_setting, 'enable-plugins')),
                ('Enable J_ava', True, 
                    self.get_browser_setting('enable-java-applet'), 
                    (self._toggle_setting, 'enable-java-applet')),
                ('Enable _Javascript', True, 
                    self.get_browser_setting('enable-scripts'), 
                    (self._toggle_setting, 'enable-scripts')),
                ('Enable _Developer Extras', True, 
                    self.get_browser_setting('enable-developer-extras'), 
                    self._browser_toggle_developer_extras),
                ('_Edit Page', True, self._browser.get_editable(),
                    lambda toggle_item: \
                            self._browser.set_editable(
                                toggle_item.get_active())),
                ('Embed Files', True, 
                    self._config.get_setting('embed-files', True),
                    lambda toggle_item: \
                            self._config.set_setting('embed-files', 
                                toggle_item.get_active(), save=True)),
                )

        for item in menu_item_tup:
            if not isinstance(item, tuple):
                menu_item = item
            else:
                label_text, use_underline, active, callback = item
                menu_item = gtk.CheckMenuItem(label_text, use_underline)
                menu_item.set_active(active)
                if isinstance(callback, tuple):
                    menu_item.connect('toggled', *callback)
                else:
                    menu_item.connect('toggled', callback)
            self._settings_menu.add(menu_item)

        self._settings_menu.show_all()

        settings_item = self._make_menu_item('gtk-preferences', 
                'Configure _Settings', 'Configure Browser settings', None)
        settings_item.set_submenu(self._settings_menu)
        settings_item.show_all()

        return settings_item

    def _setup_config(self):
        """ _setup_config -> Initialize the config with the appropriate
        settings.

        """

        settings_dict = {
                'auto-load-images': True,
                'auto-shrink-images': True, 
                'enable-plugins': True, 
                'enable-java-applet': True,
                'enable-scripts': True,
                }

        for name, value in settings_dict.iteritems():
            saved_value = self._config.get_setting(name, default=None)
            if saved_value == None: 
                self._config.set_setting(name, value, overwrite=False)
            else:
                self.set_browser_setting(name, saved_value, save=False)

    def _toggle_setting(self, toggle_button, setting_name):
        """ _toggle_setting(toggle_button, setting_name) -> Toggles the
        setting 'setting_name.'

        """

        state = toggle_button.get_active()
        self.set_browser_setting(setting_name, state)

    def take_focus(self):
        """ take_focus -> Take keybaord focus.

        """

        self._browser.grab_focus()

    def do_close(self):
        """ do_close() -> Cleanup anything specific to the inheritor.

        """

        return True

    def close(self):
        """ close() -> Default cleanup function (close temp_files).
        
        """

        self._browser.stop_loading()
        #print("%s is closing" % self.get_uri())

        # Unload the plugins.
        self._plugins.unload()
        #print('plugins unloaded')

        # Stop the file watcher.
        if self._file_watcher:
            if self._file_watcher.is_running():
                self._file_watcher.stop()
        #print('file watcher stopped')

        # Cleanup the temp files.
        for temp_file in self._temp_files:
            temp_file.close()
        #print('temp files closed')

        # Remove the browser before destroying to prevent a segfault.
        #if self._browser:
            #self._remove_browser()

        #print('returning do_close')
        return self.do_close()

    def _remove_browser(self):
        """ _remove_browser -> Remove the browser before destroying it, to
        prevent a segfault.

        """

        self._setup_browser(disconnect=True)
        self._browser.load_uri("about:blank")
        while self._browser.props.progress != 1 and \
                self._browser.props.uri != 'about:blank':
            pass

        if self._scrolled_window:
            #self._browser.set_sensitive(False)
            self._scrolled_window.remove(self._browser)
            #self._browser.unmap()
            #print('unmapped')
            #self._browser.unrealize()
            #print('unrealized')
            self._browser.destroy()
            #self._browser = None
            #del self._browser
        #print("browser removed")

    def print_message(self, message, color=0, data_color=''): 
        """ print_message(message, color=0, data_color='') -> Send a message
        to the parent object.  color is used to distinguish between different
        objects, and data_color is used for the message type.

        """

        self.emit('message', message, color, data_color)

    def set_browser_setting(self, setting, value, save=True):
        """ set_browser_setting(setting, value, save=True) -> Set the browser 
        setting 'setting' to 'value.'  If save is True then the config is set
        and saved.

        """

        if not self._browser:
            return None

        settings = self._browser.get_settings()
        settings.set_property(setting, value)

        if save:
            self._config.set_setting(setting, value)
            self._config.save()

    def set_highlight(self, find_string, case_sensitive, highlight):
        """ set_highlight(find_string, case_sensitive, highlight) -> First
        unmark all previously highlighted matches, then if highlight is True
        highlight all strings matching string 'find_string' and case, if 
        case_sensitive is True.

        """

        self._browser.unmark_text_matches()
        if highlight:
            numfound = self._browser.mark_text_matches(find_string, 
                    case_sensitive, 0)
        self._browser.set_highlight_text_matches(highlight)

    def set_history(self, history_str):
        """ set_history(history_str) -> Loads the browser with the history
        in the history_str.  The string is formated as follows: 
        current_index <seperator> title <title_uri_separator>, uri ...

        """

        if history_str:
            set_history_thread = threading.Thread(target=self._set_history, 
                    args=(history_str,))
            set_history_thread.daemon = True
            set_history_thread.start()

    def _set_history(self, history_str):
        """ _set_history(history_str) -> A helper function to be run as a 
        thread.

        """

        try:
            current_index, history_list = json.loads(history_str)
        except:
            return

        hist_list = self._browser.get_back_forward_list()

        for (title, uri) in history_list:
            item = webkit.WebHistoryItem(uri, title)
            if item:
                glib.idle_add(hist_list.add_item, item)

        if int(current_index) != 1:
            if history_list:
                glib.idle_add(self.go_to_history_item, current_index)

    def get_browser_setting(self, setting):
        """ get_browser_setting(setting) -> Return the value of the browser
        setting 'setting.'

        """

        if not self._browser:
            return None

        settings = self._browser.get_settings()
        return settings.get_property(setting)

    def get_temp_file(self):
        """ get_temp_file() -> Creates a temporary file using the tempfile
        module, and returns the file object after adding it to this modules
        _temp_files list.

        """

        temp_file = tempfile.NamedTemporaryFile()
        self._temp_files.append(temp_file)
        return temp_file

    def get_uri(self):
        """ get_uri() -> Returns the current uri for the browser.

        """

        return '%s' % self._browser.get_property('uri')

    def get_title(self):
        """ get_title() -> Returns the current title.

        """

        return '%s' % self._browser.get_property('title')

    def get_browser(self):
        """ get_browser() -> Returns the webkit.WebView object of this 
        browser.

        """

        return self._browser

    def get_history(self, index=2):
        """ get_history(index=0) -> Returns a string of the history.  The 
        string is as follows: 
        current_index <seperator> title <title_uri_separator>, uri ...

        """

        hist_list = self._browser.get_back_forward_list()
        back_hist_length = hist_list.get_back_length()

        if index == 1:
            forward_hist_length = 0
        else:
            forward_hist_length = hist_list.get_forward_length()

        if index == 2:
            current_index = back_hist_length - (back_hist_length + 
                    forward_hist_length)
        else:
            current_index = index

        return_list = [current_index]
        temp_list = []
        for i in xrange(-back_hist_length, forward_hist_length+1):
            item = hist_list.get_nth_item(i)
            if item:
                temp_list.append((item.get_title(), item.get_uri()))

        return_list.append(temp_list)
        return json.dumps(return_list)

    def _get_uri_index(self, item):
        """ _get_uri_index(item) -> If item is not none return the uri and
        index of item.  Otherwise return about:blank as the uri and 0 as
        the index.

        """

        if item:
            index = self.get_history_index(item)
            uri = item.get_uri()
        else:
            index = 0
            uri = 'about:blank'
        return uri, index

    def get_history_item(self, item_index): 
        """ get_history_item(item_index) -> Returns the uri, and index of
        the history item with the index of 'item_index' in the back forward
        history of the browser.

        """

        item = self._browser.get_back_forward_list().get_nth_item(item_index)
        return self._get_uri_index(item)

    def get_current_item(self):
        """ get_current_item() -> Returns the current uri, and the index of
        the current uri in the back forward history.

        """

        item = self._browser.get_back_forward_list().get_current_item()
        return self._get_uri_index(item)

    def get_load_status(self):
        """ get_load_status() -> Returns the current load status.

        """

        load_status = self._browser.get_load_status()
        return int(load_status)
    
    def get_history_length(self):
        """ get_history_length() -> Returns the length of the forward
        history and the back history.

        """

        hist_list = self._browser.get_back_forward_list()
        back_hist_length = hist_list.get_back_length()
        forward_hist_length = hist_list.get_forward_length()
        return back_hist_length, forward_hist_length

    def get_back_item(self):
        """ get_back_item() -> Returns the first item in the back history.

        """

        item = self._browser.get_back_forward_list().get_back_item()
        return self._get_uri_index(item)

    def get_forward_item(self):
        """ get_forward_item() -> Returns the first item in the forward 
        history.

        """

        item = self._browser.get_back_forward_list().get_forward_item()
        return self._get_uri_index(item)

    def get_back_forward_item(self, index):
        """ get_back_forward_item(index) -> Returns the item at index 'index'
        in the back forward history.  Use a negative number to get back items
        and a positive number for forward items, and zero for the current 
        page.

        """

        item = self._browser.get_back_forward_list().get_nth_item(index)
        uri = item.get_uri()
        title = item.get_title()
        return uri, title

    def get_current_history_index(self):
        """ get_current_history_index() -> Returns the index of the current
        page in the back forward history.  The index is based on whether the
        current page is backward or forward in the history of the browser
        object that owns the history list.

        """

        hist_list = self._browser.get_back_forward_list()
        back_hist_length = hist_list.get_back_length()
        forward_hist_length = hist_list.get_forward_length()
        hist_item = hist_list.get_current_item()
        for i in xrange(-back_hist_length, forward_hist_length+1):
            item = hist_list.get_nth_item(i)
            if item == hist_item:
                return i
        return 0

    def get_history_index(self, hist_item):
        """ get_history_index(hist_item) -> Returns the index of the history
        item 'hist_item.'  Indexes are based on zero being the farthest 
        forward in history.

        """

        hist_list = self._browser.get_back_forward_list()
        back_hist_length = hist_list.get_back_length()
        forward_hist_length = hist_list.get_forward_length()
        index_list = []
        for i in xrange(-back_hist_length, forward_hist_length+1):
            item = hist_list.get_nth_item(i)
            index_list.append(item)
        index = index_list.index(hist_item) - (len(index_list) -1)
        return index

    def go_to_history_item(self, index):
        """ go_to_history_item(index) -> Go forward or backward to get to the
        history item with the index of 'index.'

        """

        hist_list = self._browser.get_back_forward_list()
        item = hist_list.get_nth_item(int(index))
        self._browser.go_to_back_forward_item(item)

    def go_back(self):
        """ go_back() -> Go one step back in history.

        """

        self._browser.go_back()

    def go_forward(self):
        """ go_forward() -> Go one step forward in history.

        """

        self._browser.go_forward()

    def zoom(self, direction):
        """ zoom(direction) -> Zoom in or out depending on direction.

        """

        if direction == 1:
            self._browser.zoom_in()
        else:
            self._browser.zoom_out()

    def load_uri(self, uri):
        """ load_uri(uri) -> Load the uri in the browser object.

        """

        if uri.startswith('javascript:'):
            # Execute if uri is a javascript.
            glib.idle_add(self._browser.execute_script, uri[11:])
            self.print_message("Executing script: %s" % uri, MSGCOLOR, '38;5;64')
        elif uri.startswith('mailto:'):
            extern_load_uri(uri)
        else:
            self.print_message("Loading uri: %s" % uri, MSGCOLOR, '38;5;64')
            glib.idle_add(self._browser.load_uri, uri)

        return str(uri)

    def stop_loading(self):
        """ stop_loading() -> Stop the browser object from loading the current
        page.

        """

        self._browser.stop_loading()

    def reload(self):
        """ reload() -> Reload the current page.

        """

        self._browser.reload()

    def find(self, find_string, case_sensitive=False, forward=True, wrap=True):
        """ find(find_string, case_sensitive=False, forward=True, 
        wrap=True) -> Returns the number of matches of 'find_string.'  If 
        'case_sensitive' is True than the matches have to match the case of
        'find_string.'  If forward is True than it searches forward, and if 
        wrap is True than it wraps around when it hits the bottom of the page.

        """

        return self._browser.search_text(find_string, case_sensitive, 
                forward, wrap)

    def can_go_forward(self):
        """ can_go_forward() -> Returns True if the browser has forward 
        history.

        """

        return self._browser.can_go_forward()

    def can_go_back(self):
        """ can_go_back() -> Returns True if the browser can go back.

        """

        return self._browser.can_go_back()

    def new_browser(self):
        """ new_browser() -> Emits the 'new-browser' signal to let the parent
        know that a new browser is needed.  Also return the new browser to
        the caller.

        """

        return self.emit('new-browser')

    def open_new_tab(self, uri, flags):
        """ open_new_tab(uri, flags) -> Asks parent for a new tab loading uri.

        """

        self.emit('new-tab', uri, int(flags))

    def print_page(self):
        """ print_page() -> Ask the browser to print the current page.

        """

        webframe = self._browser.get_main_frame()
        if webframe:
            webframe.print_()

    def _grab_clipboard(self):
        """ _grab_clipboard() -> Grab the clipboard so the webview can be
        destroyed without causing a segfault.

        """

        # Grab ownership of the clipboard so webkit doesn't segfault.
        clipboard = gtk.clipboard_get('PRIMARY')
        selected_text = clipboard.wait_for_text()
        if selected_text:
            clipboard.set_text(selected_text)
            clipboard.store()

    def _open_address(self, openlink_item, event, selection):
        """ _open_address(openlink_item, event, selection) -> Open the address
        in selection.

        """

        self.open_new_tab(selection, event.state)

    def _show_hide_download(self, show_hide_download_item, event):
        """ _show_hide_term(show_hide_download_item, event) -> Let the parent
        know that it should toggle the download managers visibility.

        """

        self.emit('show-hide-download')

    def _save_as(self, save_as_item, event):
        """ _save_as(save_as_item, event) -> Handles saving of the current
        page.

        """

        uri = self._browser.get_property('uri')

        # Only try to save the page if it has a uri.
        if uri:
            filename = uri.split('/')[-1]
        else:
            return False

        save_dialog = SaveDialog(filename, self._current_folder)
        new_filename = save_dialog.run()

        if new_filename:
            # If the user did not cancel the operation then save the page to
            # 'new_filename.'
            with open(new_filename, 'w') as out_file:
                source = self._browser.get_main_frame().get_data_source()
                out_file.write(source.get_data())

    def _view_source(self, view_source_item, event, external=False):
        """ _view_source(view_source_item, event, external=False) -> View
        the source of the current page.  If external is True than use the
        external editor (default is 'gvim').

        """

        if not external:
            if event.button == 2:
                # Load the page in another tab and view its source
                browser = self.new_browser().get_browser()
                browser.set_view_source_mode(True)
                browser.load_uri(self.get_uri())
            else:
                # View the source in the current tab
                self._browser.set_view_source_mode(not 
                        self._browser.get_view_source_mode())
                self._browser.reload()
        else:
            top_frame = self._browser.get_main_frame()
            data_source = top_frame.get_data_source()
            source = data_source.get_data()
            if not source:
                return
            temp_file = self.get_temp_file()
            temp_file.write(source)
            temp_file.flush()
            extern_load_uri('file://%s' % temp_file.name)

    def _replace_word(self, word_item, event):
        """ _replace_word(word_item, event) -> Replace the selected word with
        the title of the current item.

        """

        clipboard = gtk.clipboard_get('CLIPBOARD')

        # Save the current contents of the clipboard.
        old_text = clipboard.wait_for_text()

        # Put the replacement word in the clipboard and paste it.
        clipboard.set_text(word_item.get_label())
        clipboard.store()
        self._browser.paste_clipboard()

        # Restore the old clipboard contents if there were any.
        if old_text:
            clipboard.set_text(old_text)
            clipboard.store()

    def _search_web(self, search_web_item, event, search_engine=None, 
            search_menu_item=None):
        """ _search_web(search_web_item, event, search_engine=None, 
        search_menu_item=None) -> Search the Internet for the current 
        selection using 'search_engine.'


        """

        if search_menu_item:
            # Function was called when an item in the search menu was clicked.
            # So popdown the main menu.
            search_menu_item.parent.popdown()

        # I don't know how else to get the selected text so I use the 
        # 'PRIMARY' (e.g. selection) clipboard.
        clipboard = self._browser.get_clipboard(selection='PRIMARY')
        search_string = clipboard.wait_for_text()
        if search_string:
            search_uri = self._search_engine_menu.get_uri(search_string, 
                    search_engine)
            self.open_new_tab(search_uri, event.state)

    def _print_page(self, print_item, event):
        """ _print_page(print_item, event) -> The print page item was clicked.
        So do the correct thing.

        """

        print_item.parent.popdown()
        self.print_page()

    def _send_title(self, title):
        """ _send_title(title) -> Send the 'title' to parent.

        """

        if not title:
            title = self.get_uri()
        self.emit('title-changed', title)

    def _send_download(self, uri, filename=None):
        """ _send_download(uri, filename=None) -> Send 'uri' and an optional
        filename to the parent to be downloaded.

        """

        if not filename:
            # Make up a filename because none was given.
            filename = uri.split('/')[-1]
            if not filename:
                # If all else fails use the uri as the filename.
                filename = uri
        self.emit('download-uri', filename, uri)

    def _send_back_forward(self):
        """ _send_back_forward() -> Notify parent if the browser can go
        back and/or forward.

        """

        can_go_back = self._browser.can_go_back()
        can_go_forward = self._browser.can_go_forward()
        self.emit('back-forward', can_go_back, can_go_forward)

    def _browser_toggle_developer_extras(self, toggle_item):
        """ _browser_toggle_developer_extras -> Enable/Disable the developer
        extras.  Hide the web inspector panel if the developer extras are
        disabled.

        """

        enabled = toggle_item.get_active()

        if not enabled and self._web_inspector:
            self._web_inspector.emit('close-window')
            self._web_inspector = None
            return

        # This tabs web-inspector object.
        self._web_inspector = self._browser.get_web_inspector()

        inspector_connection_dict = {
                'inspect-web-view': self._browser_inspect_web_view,
                'detach-window': self._browser_inspect_detach,
                'attach-window': self._browser_inspect_attach,
                'close-window': self._browser_inspect_close,
                'finished': self._browser_inspect_finished,
                'show-window': self._browser_inspect_show,
                'notify::inspected-uri': self._browser_inspect_uri,
                }

        for signal, handler in inspector_connection_dict.iteritems():
            self._web_inspector.connect(signal, handler)

        self.set_browser_setting('enable-developer-extras', enabled)
        
    def _browser_print(self, webview, webframe):
        """ _browser_print(webview, webframe) -> Handle the print signal
        from browser.

        """

        # Use the default print dialog to print the page.
        webframe.print_()
        return True

    def _browser_icon_loaded(self, webview, icon_uri):
        """ _browser_icon_loaded(webview) -> Handles the browser-icon-loaded
        signal from browser.

        Doesn't seem to do anything.

        """

        self.print_message("icon loaded: %s" % icon_uri, MSGCOLOR)

        # Send the icon_uri to the parent.
        self.emit('favicon-uri', icon_uri)

    def _browser_resource_request_starting(self, webview, webframe, resource, 
            request, response):
        """ _browser_resource_request_starting -> Logs all resource requests.  

        """

        uri = request.get_uri()
        if 'stream.php' in uri:
            print(resource.get_data())

        result = self.emit('resource-request', uri)
        self.print_message("resource request: %s" % uri, MSGCOLOR, '38;5;69')

        if type(result) == str:
            request.set_uri(result)

    def _browser_mime_decision_requested(self, webview, webframe, request, 
            mimetype, policy_decision):
        """ _browser_mime_decision_requested -> If the mime-type is not 
        loadable than either embed it or download it.

        """

        self.print_message("mime requested: %s (uri=%s)" % (mimetype, 
            request.get_uri()), MSGCOLOR, '38;5;202')
        if not webview.can_show_mime_type(mimetype):
            handler_cmd_str = self._mime_handler_dict.get(mimetype, None)
            if handler_cmd_str and \
                    self._config.get_setting('embed-files', True):
                self.emit('embed-mime-uri', mimetype, request.get_uri(), 
                        handler_cmd_str)
            else:
                policy_decision.download()
                return True

        return False

    def _browser_nav_policy_request(self, webview, webframe, request, 
            nav_action, policy_decision):
        """ _browser_nav_policy_request -> Handles opening new tabs if links
        are middle clicked, or control clicked.

        """

        if nav_action.get_button() == 2 or (nav_action.get_button() == 1 and 
                nav_action.get_modifier_state() & gtk.gdk.CONTROL_MASK):
            self.open_new_tab(request.get_uri(), 
                    nav_action.get_modifier_state())
            return True

        self.print_message("navigation policy requested: %s" % \
                request.get_uri(), MSGCOLOR, '38;5;93')

        return False

    def _browser_create_plugin(self, webview, mime_type, uri, param):
        """ _browser_create_plugin -> Logs plugin creation.

        """

        result = self.emit('plugin-request', uri)
        self.print_message("plugin requested: %s mime %s" % (uri, \
                mime_type), MSGCOLOR, '38;5;88')
        if type(result) == gtk.Widget:
            return result

    def _browser_download_requested(self, webview, download):
        """ _browser_download_requested -> Send all downloads to the parent.

        """

        uri = download.get_uri()
        filename = download.get_suggested_filename()
        self._send_download(uri, filename)
        return False

    def _browser_console_message(self, webview, message, line, source_id):
        """ _browser_console_message -> Prints any message the browser emits.

        """

        self.print_message("console message: line %d: %s (id %s)" % (line, \
                message, source_id), MSGCOLOR, '38;5;196')
        return True

    def _browser_property_changed(self, webview, property):
        """ _browser_property_changed -> Handles browser property changes.

        """

        #print("%s %s" % (property.name, webview.get_property(property.name)))
        pass

    def _browser_uri_changed(self, webview, property):
        """ _browser_uri_changed -> If the uri changes than tell the parent
        whether it has back forward history.

        """

        self.emit('uri-changed', webview.get_property('uri'))
        self._send_back_forward()

    def _browser_new_webview(self, webview, webframe):
        """ _browser_new_webview -> If the browser requests a new webview
        than tell the parent to make one.

        """

        browser_view = self.new_browser()
        if self._key_flags:
            if gtk.gdk.SHIFT_MASK & self._key_flags:
                uri, index = self.get_current_item()
                browser_view.set_history(self.get_history(index))
        return browser_view.get_browser()

    def _browser_new_window(self, webview, webframe, request, nav_action, 
            policy):
        """ _browser_new_window -> Log when a new window is requested.

        """

        self.print_message('new window request: %s' % request.get_uri(), 
                MSGCOLOR, '38;5;64')

    def _browser_popup(self, webview, menu):
        """ _browser_popup -> Add and customize items in the browsers popup
        menu, based on why the menu was popped up.

        """

        if not menu.get_children():
            # Don't add a separator item if there were no items to begin with.
            menu_item_tup = ()
        else:
            menu_item_tup = (gtk.SeparatorMenuItem(),)

        if self._hover_uri:
            # If a link was right-clicked then change the 'open in new window'
            # item to be 'Open in new tab.'
            new_window_item = menu.get_children()[1]
            new_window_item.get_children()[0].set_text("Open in _new tab")
            new_window_item.set_use_underline(True)

        if webview.has_selection():
            clipboard = self._browser.get_clipboard(selection='PRIMARY')
            selection = clipboard.wait_for_text()
            if selection:
                #item_list = menu.get_children()
                #search_web_item = None
                #last_spell_index = None
                #for index in xrange(len(item_list)):
                    #item_label = item_list[index].get_label()
                    #if item_label == "_Search the Web":
                        #search_web_item = item_list[index]
                        #search_web_index = index
                        #break
                    #elif item_label == "_Ignore Spelling":
                        #last_spell_index = index - 1

                #if last_spell_index:
                    #for index in xrange(last_spell_index):
                        #item_list[index].connect('button-release-event',
                                #self._replace_word)

                search_web_index = 0
                search_web_item = self._make_menu_item('gtk-find', 
                        'Search Web', 'Search for the selected text.', 
                        self._search_web)
                menu.insert(search_web_item, search_web_index)
                if search_web_item:
                    # Customize the search web item.
                    #search_web_item.connect('button-release-event', 
                            #self._search_web)
                    # Add the search menu.
                    if self._search_menu_item.get_parent():
                        self._search_menu_item.unparent()
                    menu.insert(self._search_menu_item, search_web_index + 1)

                if '.' in selection and ' ' not in selection:
                    # Add the Open address in new tab item when the
                    # selection looks like it could be a uri.
                    menu.add(gtk.SeparatorMenuItem())

                    openlink_item = self._make_menu_item('go-jump', 
                            'Open Address in New Tab', 
                            'Open selected address in new tab.', 
                            self._open_address, selection)
                    menu.add(openlink_item)

        # Always show the view source and settings menu.
        view_source_item = gtk.CheckMenuItem("_View Source", True)
        view_source_item.set_active(self._browser.get_view_source_mode())
        view_source_item.connect('button-release-event', self._view_source)

        menu_item_tup += (
                ('gtk-print', 'Print Page', 'Print page', self._print_page),
                gtk.SeparatorMenuItem(),
                ('gtk-save-as', 'Save Page As...', 'Save page as...', 
                    self._save_as),
                gtk.SeparatorMenuItem(),
                view_source_item,
                ('gtk-edit', 'View Source in _Editor', 
                    'Opens the page source in external editor.', 
                    self._view_source, True),
                gtk.SeparatorMenuItem(),
                ('emblem-downloads', '_Show/Hide Download Manager', 
                    'Show or hide the download manager', 
                    self._show_hide_download),
                gtk.SeparatorMenuItem(),
                self._settings_item(),
                self._plugins_item(),
                )

        for item in menu_item_tup:
            if type(item) != tuple:
                menu_item = item
            else:
                menu_item = self._make_menu_item(*item)
            menu.add(menu_item)

        self.emit('populate-popup', menu)
        menu.show_all()

    def _browser_hovering_over_link(self, webview, title, uri):
        """ _browser_hovering_over_link -> Save the uri and emit the hover-uri
        signal.

        """

        self._hover_uri = uri
        self.emit('hover-uri', str(uri))

    def _browser_inspect_detach(self, inspector):
        """ _browser_inspect_detach -> Make the inspector appear in its own
        window.

        """

        webview = inspector.get_web_view()
        if webview:
            window = gtk.Window()
            x, y, width, height = webview.get_allocation()
            if width <= 1 or height <= 1:
                x, y, width, height = self.get_allocation()
                pos = self.get_position()
                if pos != 0:
                    width -= pos
                else:
                    width /= 2
            window.set_size_request(width, height)
            window.set_resizable(True)
            window.set_title("%s - Web Inspector" % self.get_title())
            if webview.parent:
                webview.reparent(window)
            else:
                window.add(webview)
            window.show_all()

        return True

    def _browser_inspect_attach(self, inspector):
        """ _browser_inspect_attach -> Attach the inspector to the main
        window.

        """

        webview = inspector.get_web_view()
        if webview:
            x, y, width, height = webview.get_allocation()
            selfx, selfy, selfwidth, selfheight = self.get_allocation()
            self.set_position(selfwidth-width)
            if webview.parent:
                window = webview.parent
                webview.reparent(self)
                window.destroy()

        return True

    def _browser_inspect_close(self, inspector):
        """ _browser_inspect_close -> Close the web inspector.

        """

        # Unselect everything.
        self._grab_clipboard()

        webview = inspector.get_web_view()
        if webview:
            if webview.parent:
                # Save the window while we still can.
                window = webview.parent
                webview.parent.remove(webview)

                # Destroy the detached window.
                if type(window) == gtk.Window:
                    window.destroy()

                webview.destroy()

        return True

    def _browser_inspect_uri(self, inspector, property):
        """ _browser_inspect_uri -> Change the window title when the uri
        changes.

        Currently it does not work.

        """

        print(inspector.get_property(property.name))

    def _browser_inspect_show(self, inspector):
        """ _browser_inspect_show -> Show the web inspector.

        """

        webview = inspector.get_web_view()
        if webview:
            if webview.parent:
                window = webview.parent
                if window:
                    window.show_all()
            else:
                self._browser_inspect_detach(inspector)

        return True

    def _browser_inspect_finished(self, inspector):
        """ _browser_inspect_finished -> Cleanup when the web inspector is
        finished.

        """

        print("Finished")

    def _browser_inspect_web_view(self, inspector, webview):
        """ _browser_inspect_web_view -> Return a new webview to be used by 
        the web inspector.

        """

        return webkit.WebView()

    def _browser_key_press(self, webview, event):
        """ _browser_key_press -> Do stuff if a key is pressed.

        """

        #print(webview.get_focus_child())
        return False

    def _browser_button_press_event(self, webview, event):
        """ _browser_button_press_event -> Save the key flags when the mouse
        is clicked.

        """

        self._key_flags = event.state

        return False

    def _browser_scroll_event(self, webview, event):
        """ Handle the scroll wheel events.

        """

        if event.state & gtk.gdk.CONTROL_MASK:
            if event.direction == gtk.gdk.SCROLL_UP:
                # Zoom in.
                webview.zoom_in()
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                # Zoom out.
                webview.zoom_out()
            return True

        return False

    def _browser_title_changed(self, webview, property):
        """ _browser_title_changed -> Send the new title to the parent, and
        try and get the favicon uri from the webpage source to send as well.

        """

        title = webview.get_property(property.name)
        self._send_title(title)

        # This tabs web-inspector object.
        if self._web_inspector:
            inspector_view = self._web_inspector.get_web_view()
            if inspector_view:
                if isinstance(inspector_view.parent, gtk.Window):
                    inspector_view.parent.set_title("%s - Web Inspector" % 
                            self.get_title())

        # Skip the rest of the method, because it is not needed anymore.
        return

        # Get the source of the page.
        top_frame = webview.get_main_frame()
        data_source = top_frame.get_data_source()
        source = data_source.get_data()

        # Skip the favicon if the source is empty:
        if not source:
            return

        # Regex patterns to find the favicon uri.
        is_icon_pat = re.compile(r"""rel=("|')(shortcut icon|icon)""", re.I)
        icon_pat = re.compile(r"""href=("|')(.*)("|')""", re.I)

        # Set a default uri.
        icon_uri = '/favicon.ico'

        # Loop by line through the source until a match is found, or until
        # the end of the source is reached.
        for line in source.splitlines():
            if is_icon_pat.search(line):
                match = icon_pat.search(line)
                if match:
                    # A match was found so save the uri from it and exit the 
                    # loop.
                    icon_uri = match.groups()[1].split()[0]
                    icon_uri = icon_uri.strip('"').strip("'")
                    break

        # Send the icon_uri to the parent.
        self.emit('favicon-uri', icon_uri)

    def _browser_load_status_changed(self, webview, property):
        """ _browser_load_status_changed -> Notify the parent if the page has
        started or finished loading.

        """

        load_status = webview.get_property(property.name)
        self.emit('load-status', load_status)

        if load_status == 0:
            # No data has been sent but loading has started.
            self.emit('progress-changed', 0.0)
            self._send_title('Loading...')
        elif load_status == 1:
            # Load has been committed.
            self.print_message("Load Committed.", MSGCOLOR)
        elif load_status == 2:
            # All the data necessary to display the page has been loaded.
            self.emit('progress-changed', 1.0)
            self._send_title(webview.get_property('title'))

    def _browser_progress_changed(self, webview, property):
        """ _browser_progress_changed -> The progress has changed so notify
        the parent what it is now.

        """

        progress = webview.get_property(property.name)
        self.emit('progress-changed', progress)
        if progress == 0:
            self._send_title('Loading...')
        elif progress == 1:
            self._send_title(webview.get_property('title'))
            self.emit('load-status', 2)

    def _browser_view_ready(self, webview):
        print "ready"
