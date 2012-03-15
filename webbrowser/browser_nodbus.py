# This file is part of browser, and contains the BrowserTab class for a tab 
# that does not use dbus.
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

import json
from optparse import OptionParser

import gtk

from browser_classes import BrowserTabBase, BrowserBase, MSGCOLOR
from browserplug_classes import BrowserView

class BrowserTab(BrowserTabBase):

    def __init__(self, popup=False, uri=None, history_str='', history_index=1, profile='default'):
        super(BrowserTab, self).__init__(popup=popup, uri=uri, history_str=history_str, history_index=history_index, profile=profile)

        self._browser_view = BrowserView(self._profile)
        self._connect_browser()

        self._type = 'BrowserTab'

        self.pack_start(self._browser_view, True)
        self.reorder_child(self._browser_view, 1)

        if history_str:
            self._browser_view.set_history(history_str)

        if self._uri:
            if self._history_index == 1:
                self.load_uri(self._uri)
        else:
            self._uri = 'about:blank'

        self.show_all()

    def _connect_browser(self):
        browser_connect_dict = {
            'new-browser' : self._browser_new_browser,
            'new-tab' : self._browser_new_tab,
            'title-changed' : self._browser_title_changed,
            'back-forward' : self._browser_back_forward,
            'download-uri' : self._browser_download_uri,
            'embed-mime-uri' : self._browser_embed_mime_uri,
            'uri-changed' : self._browser_uri_changed,
            'hover-uri' : self._browser_hover_uri,
            'favicon-uri' : self._browser_favicon_uri,
            'progress-changed' : self._browser_progress_changed,
            'show-hide-download' : self._browser_show_hide_download,
            'message' : self._browser_message,
            }

        for signal, callback in browser_connect_dict.iteritems():
            if type(callback) == tuple:
                self._browser_view.connect(signal, *callback)
            else:
                self._browser_view.connect(signal, callback)

    def get_browser(self):
        return self._browser_view.get_browser()

    def get_browser_window(self):
        return self._browser_view

    def take_focus(self):
        """ take_focus -> Take keybaord focus.

        """

        self._browser_view.take_focus()

    def print_page(self):
        self._browser_view.print_page()

    def refresh_page(self):
        self._browser_view.reload()

    def stop_loading(self):
        self._browser_view.stop_loading()

    def do_close(self):
        if self._browser_view:
            if self._browser_view.close():
                # Destroy the web view in an attempt to prevent a segfault.
                # I'm not sure if it works.
                self._browser_view.destroy()
                #print('browser view destroyed')
                return True
            else:
                self._browser_view.destroy()
                #print('browser view destroyed')
                return False
        else:
            return False

    def do_zoom(self, direction):
        """ do_zoom(direction) -> Zoom in or out depending on direction.
        
        """

        self._browser_view.zoom(direction)

    def do_get_history(self, index=2):
        return self._browser_view.get_history(index)

    def do_highlight_toggled(self, find_string, match_case, highlight_match):
        return self._browser_view.set_highlight(find_string, match_case, highlight_match)

    def do_set_highlight(self, find_string, match_case, highlight):
        return self._browser_view.set_highlight(find_string, match_case, highlight)

    def do_find(self, find_string, match_case, find_direction, wrap_find):
        return self._browser_view.find(find_string, match_case, find_direction, wrap_find)

    def do_go_to(self, uri):
        if self._browser_view:
            self._browser_view.load_uri(uri)
            self._page_loading = True
        else:
            self._uri=uri

    def do_get_history_length(self):
        return self._browser_view.get_history_length()

    def do_get_back_forward_item(self, index):
        return self._browser_view.get_back_forward_item(index)

    def do_get_current_item(self):
        return self._browser_view.get_current_item()

    def do_get_back_item(self):
        return self._browser_view.get_back_item()

    def do_get_forward_item(self):
        return self._browser_view.get_forward_item()

    def do_get_history_item(self, index):
        return self._browser_view.get_history_item(index)

    def do_go_to_history_item(self, index):
        self._browser_view.go_to_history_item(index)

    def do_go_back(self):
        self._browser_view.go_back()

    def do_go_forward(self):
        self._browser_view.go_forward()
        
    def _browser_message(self, browser_window, message, color, data_color):
        self.print_message('browser_window: %s' % message, color, data_color)

    def _browser_new_browser(self, browser_window):
        return self.emit('browser-new-tab', {'popup':True}).get_browser_window()

    def _browser_new_tab(self, browser_window, uri, flags):
        self.emit('browser-new-tab', {'flags':flags, 'uri':uri})

    def _browser_hover_uri(self, browser_window, uri):
        self.do_receive_hover_uri(uri)

    def _browser_back_forward(self, browser_window, can_go_back, can_go_forward):
        self.do_receive_back_forward(can_go_back, can_go_forward)

    def _browser_title_changed(self, browser_window, title):
        self.do_receive_title(title)

    def _browser_uri_changed(self, browser_window, uri):
        self.do_receive_uri(uri)

    def _browser_favicon_uri(self, browser_window, icon_uri):
        self.do_receive_favicon_uri(icon_uri)

    def _browser_progress_changed(self, browser_window, progress):
        self.do_receive_progress(progress)

    def _browser_show_hide_download(self, browser_window):
        self.emit('toggle-download-manager')

    def _browser_download_uri(self, browser_window, filename, uri):
        self.emit('download-uri', filename, uri)

    def _browser_embed_mime_uri(self, browser_window, mimetype, uri, handler_cmd_str):
        self.emit('embed-mime-uri', mimetype, uri, handler_cmd_str)

class Browser(BrowserBase):

    def __init__(self, uri=None, width=1213, height = 628):
        super(Browser, self).__init__(uri=uri, width=width, height=height)

        if uri:
            # Open a tab if there was a uri given.
            self.do_open_tab(uri=uri)

    def do_browser_closed(self, browsebox):
        """ do_browser_closed(browsebox) -> Clean up after a tab is closed.

        """

        self.print_message("main: tab closed", MSGCOLOR)

    def new_tab(self, uri=None, popup=False, history_str='', history_index=1):

        browsebox = BrowserTab(popup=popup, uri=uri, 
                history_str=history_str, history_index=history_index)

        self.do_new_tab(browsebox, uri, popup)

        self.print_message("main: tab added", MSGCOLOR)

        return browsebox

    def do_open_tab(self, flags=0, tab=None, uri=None, popup=False, 
            pid=None, history_str='', history_index=1):

        if not tab:
            tab = self._current_tab

        if not gtk.gdk.SHIFT_MASK & flags:
            history_index = 1
        else:
            # If shift was held down, and 'history_str' is not set, than 
            # copy the history of 'tab' into the new tab.
            if not history_str and tab:
                history_str = tab.do_get_history(history_index)

        new_tab = self.new_tab(uri=uri, popup=popup, 
                history_str=history_str, history_index=history_index) 

        return new_tab

    def do_restore_tab(self, tab_dict, flags):
        """ do_restore_tab(tab_dict, flags) -> Restores a tab based on 'tab_dict'.
        flags holds the key masks of the modifier keys that were pressed.

        """
        
        info_list = tab_dict['info_list']
        if isinstance(info_list, dict):
            # New type
            tab_pid = info_list['pid']
            tab_state = info_list['state']
            hist_list = info_list['history']
        else:
            tab_pid, tab_state, hist_list = info_list

        history_str = json.dumps(hist_list)
        tab_index = int(tab_dict['index'])

        browsebox = self.do_open_tab(flags=flags, 
                history_str=history_str)

        self._browser_book.reorder_child(browsebox, tab_index)
        self._browser_book.set_tab_state(browsebox, tab_state)

    @classmethod
    def do_create_window(cls, browsebox=None, uri=None):
        """ Create a new window.

        """

        return Browser(uri=uri)

if __name__ == "__main__":
    opts = OptionParser("usage: %prog [options]")
    opts.add_option("-u", "--uri", action="store", type="string", dest="uri", help="Load uri")

    options, args = opts.parse_args()
    if args:
        opts.print_help()
        exit(1)

    Browser.do_create_window(uri=options.uri).run()
