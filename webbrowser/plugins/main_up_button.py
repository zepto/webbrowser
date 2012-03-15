# This file is part of browser.  This plugin adds a up button to each tabs 
# toolbar.
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

""" Places a button on each tabs toolbar to go up a level from the current
uri.

"""

import os

import gtk

from browser_classes import BrowserTabBase

class UpButton(object):
    """ A button for going up a level from the current uri.

    """

    def __init__(self, browser):
        """ Initialize some basic things.

        """

        self._browser = browser
        self._item_dict = {}

    def run(self):
        """ Connect to some signals, and add the up button to all the open tabs.

        """

        try:
            self._browser._browser_book.connect('page-added', self._tab_added)
            self._browser._browser_book.connect('page-removed', 
                    self._tab_removed)
            self._browser._browser_book.connect('create-window', 
                    self._create_window)
            for tab in self._browser._browser_book.get_children():
                self._tab_added(self._browser._browser_book, tab, 
                        self._browser._browser_book.page_num(tab))
        except:
            pass

    def exit(self):
        """ Disconnect from the signals and remove the button from all the tabs.

        """

        try:
            self._browser._browser_book.disconnect_by_func(self._tab_added)
            self._browser._browser_book.disconnect_by_func(self._tab_removed)
            self._browser._browser_book.disconnect_by_func(self._create_window)
        except:
            pass
        finally:
            item_dict = {}
            item_dict.update(self._item_dict)
            for tab, item in item_dict.iteritems():
                self._tab_removed(self._browser._browser_book, tab, 
                        self._browser._browser_book.page_num(tab))

    def _tab_added(self, browser_book, tab, index):
        """ When a tab is added create a button an add it to the tabs toolbar.

        """

        # Only add it if the tab is a browser tab.
        if not isinstance(tab, BrowserTabBase):
            return

        # A tuple containing the settings for the button.
        up_button_tup = ('_up_button', ('up', True, 
            'Go up a level.', self._up_clicked, tab))

        (button_name, settings) = up_button_tup
        item = gtk.ToolItem()
        item.add(tab._toolbar_button(*settings))

        # Enable or disable the button based on whether it looks like the
        # uri can go up a level or not.
        uri = tab.get_uri()
        if uri:
            item.set_sensitive(len(uri.strip('/').split('/')) > 3)
        else:
            item.set_sensitive(False)
        item.show_all()
        self._item_dict[tab] = item
        tab._address_bar.insert(item, 3)

        # Update the button when the title changes.
        tab.connect('title-changed', self._update_item)

    def _tab_removed(self, browser_book, tab, index=None):
        """ Remove the button from tab.

        """

        item = self._item_dict.pop(tab, None)
        if item:
            tab._address_bar.remove(item)

    def _create_window(self, browser_book, tab, x, y):
        """ Remove item from tab.

        """

        self._tab_removed(browser_book, tab)

    def _update_item(self, tab, title):
        """ Enable or disable the button based on the uri.

        """

        item = self._item_dict.get(tab, None)
        if item:
            item.set_sensitive(len(tab.get_uri().strip('/').split('/')) > 3)

    def _up_clicked(self, up_button, event, tab):
        """ Strip from the last / to the end of the uri to go up a level.

        """

        uri = tab.get_uri()
        if uri:
            level_list = uri.strip('/').split('/')
            if len(level_list) > 3:
                level_list.pop()
                new_uri = '/'.join(level_list)
            else:
                new_uri = uri
        else:
            return False

        if event.button == 2:
            self._browser.do_open_tab(flags=event.state, tab=tab, uri=new_uri)
        else:
            tab.load_uri(new_uri)

Plugin = UpButton
