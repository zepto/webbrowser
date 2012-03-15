# This file is part of browser.  This is a plugin to block ads.
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

""" A tab plugin that watches requests and blocks ads.

"""

import re
import os

import gtk
import pango
from glib import get_user_config_dir, timeout_add

class AdBlock(object):
    """ AdBlock -> Load ad patterns from a file and block requests to uris
    that match any of those patterns.

    """

    def __init__(self, tab):
        """ Initialize the ad blocker.

        """

        self._path = '%s/webbrowser' % get_user_config_dir()
        self._ad_pat = None
        self._tab = tab
        self._log_func = tab.print_message
        self._enabled = True
        self._file_watch = tab._file_watcher
        #self._file_watch = None

    def run(self):
        """ Do the final initialization and run the ad blocker.

        """

        if not os.path.isfile('%s/block.uri' % self._path):
            with open('%s/block.uri' % self._path, 'w') as block_file:
                block_file.write('# Add block file\n\n')

        self._log_func("(Ad Block plugin): Running.", 32, '1;38;5;196')
        self.setup_ad_pat()
        self._toggle_file_watch()

        # Connect the ad blocker to browser.
        self._tab.connect('resource-request', self._block_resource) 
        self._tab.connect('plugin-request', self._block_plugin) 
        self._tab.connect('populate-popup', self._popup) 

    def exit(self):
        """ exit -> Disconnect and stop the ad blocker.

        """

        try:
            self._toggle_file_watch()
            self._tab.disconnect_by_func(self._block_resource)
            self._tab.disconnect_by_func(self._block_plugin)
            self._tab.disconnect_by_func(self._popup)
        except:
            # Ignore errors.
            pass

    def setup_ad_pat(self):
        """ setup_ad_pat -> Setup the ad regex pattern.

        """

        pattern_list = []
        with open('%s/block.uri' % self._path, 'r') as block_file:
            for line in block_file.readlines():
                if line[0] != '#' and line.strip():
                    pattern_list.append(line.strip())

        ad_str = r'|'.join(pattern_list)
        self._ad_pat = re.compile(r'(%s)' % ad_str, re.I)

    def _toggle_file_watch(self):
        """ _toggle_file_watch -> Toggle the file watcher.

        """

        if self._file_watch:
            filename = '%s/block.uri' % self._path
            if not self._file_watch.has_file(filename):
                self._file_watch.add_file(filename, self._reload_ad_pat)
            else:
                self._file_watch.remove_file(filename)

    def _reload_ad_pat(self, *args):
        """ _reload_ad_pat -> Re-load the ad block information from the file.

        """

        self._log_func("(Ad Block plugin) Re-loading blocking information.",
                32, '1;38;5;196')
        self.setup_ad_pat()

    def _block_plugin(self, tab, uri):
        """ _block_plugin -> Check plugin uris against the ad retext pattern,
        and if they match it blocks them.

        """

        if not self._enabled:
            return

        match = self._ad_pat.search(uri)
        if match:
            self._log_func("(Ad Block plugin) blocking plugin: %s" % uri, 
                    32, '1;38;5;196')
            pl = gtk.Label("Blocked: %s" % uri)
            pl.set_line_wrap_mode(pango.WRAP_WORD_CHAR)

    def _block_resource(self, tab, uri):
        """ _block_resource -> Watches resource requests and blocks the ones 
        that match a certain pattern.

        """

        if not self._enabled:
            return

        match = self._ad_pat.search(uri)
        if match:
            if self._log_func:
                self._log_func("(Ad Block plugin) blocking resource: %s" % 
                        uri, 32, '1;38;5;196')
            return 'about:blank'

    def _toggle_adblocker(self, menuitem):
        """ _toggle_adblocker -> Enable/disable the ad-blocker.

        """

        self._enabled = menuitem.get_active()
        if self._enabled:
            self.setup_ad_pat()
        self._toggle_file_watch()

    def _popup(self, tab, menu):
        """ _popup -> Builds and adds a menu item to enable/disable the 
        ad-blocker.

        """

        try:
            menu_item = gtk.CheckMenuItem('Enable Ad-Blocker')
            menu_item.set_active(self._enabled)
            menu_item.connect('toggled', self._toggle_adblocker)
            menu_item.show_all()
            self._tab._settings_menu.add(menu_item)
        except Exception as err:
            self._log_func("(Ad Block plugin): Error adding menu item: %s" % err, 32, '1;38;5;196')

Plugin = AdBlock
