# This file is part of browser.  This is a plugin to set a proxy.
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

""" A tab plugin that sets webkit proxy to environment variable
http_proxy.

"""
import ctypes
import os
import glob

import gtk
from glib import get_user_config_dir

from defaults import APP_NAME

class Proxy(object):
    """ Proxy -> Sets proxy.

    """

    def __init__(self, tab):
        """ Initialize the proxy setter.

        """

        self._tab = tab
        self._log_func = tab.print_message
        self._enabled = True

    def run(self):
        """ Do the final initialization and run.

        """

        self._log_func("(Proxy plugin): Running.", 32, '38;5;196')
        self._set_proxy()

        # Connect to the browser.
        self._tab.connect('populate-popup', self._popup)

    def exit(self):
        """ exit -> Disconnect and stop.

        """

        try:
            self._set_proxy(False)
            self._tab.disconnect_by_func(self._popup)
        except:
            # Ignore errors.
            pass

    def _set_proxy(self, load=True):
        """ _load_proxy(load=True) -> Set the proxy if load is true.

        """

        try:
            if load:
                proxy = os.getenv('http_proxy')
            else:
                proxy = ''
            import ctypes
            from ctypes.util import find_library
            libgobject =ctypes.cdll.LoadLibrary(find_library('gobject-2.0'))
            libsoup = ctypes.cdll.LoadLibrary(find_library('soup-2.4'))
            libwebkit = ctypes.cdll.LoadLibrary(find_library('webkit-1.0'))
            proxy_uri = libsoup.soup_uri_new(proxy)
            session = libwebkit.webkit_get_default_session()
            libgobject.g_object_set(session, "proxy-uri", proxy_uri, None)
        except:
            pass

    def _toggle(self, menuitem):
        """ _toggle -> Enable/disable style loader.

        """

        self._enabled = not self._enabled
        if not self._enabled:
            self._set_proxy(False)
        else:
            self._set_proxy()


    def _popup(self, tab, menu):
        """ _popup -> Builds and adds a menu item to enable/disable the 
        stylesheet loader.

        """

        try:
            menu_item = gtk.CheckMenuItem('Enable Proxy')
            menu_item.set_active(self._enabled)
            menu_item.connect('toggled', self._toggle) 
            menu_item.show_all()
            self._tab._settings_menu.add(menu_item)
        except Exception as err:
            self._log_func("(Proxy plugin):  Error adding menu item: %s" % err, 32, '38;5;196')

#Plugin = Proxy
