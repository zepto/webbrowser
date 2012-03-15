# This file is part of browser, and contains the plugin to view messages.
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

""" Message view plugin for the browser.

"""
import gtk
import pango
import glib
import threading
from time import strftime

from classes import LogView

class MessageView(object):

    def __init__(self, browser):

        self._browser = browser
        self._debug_view = None

    def run(self):
        # Start debug view
        self._debug_view = LogView()
        self._browser.connect('message', self.print_message)
        self._browser._term_book.new_tab(self._debug_view)
        self._browser._term_book.reorder_child(self._debug_view, 0)

        keyval, modifier = gtk.accelerator_parse('<Control><Shift>c')
        self._browser._accels.connect_group(keyval, modifier, 
                gtk.ACCEL_VISIBLE, self._toggle_terminal_key_pressed)

        self.print_message(self._browser, 'Message View plugin started.')

    def exit(self):
        try:
            self._browser.disconnect_by_func(self.print_message)
            self._browser._accels.disconnect_by_func(self._toggle_terminal_key_pressed)
        except Exception as err:
            print(err)
        finally:
            self._browser._term_book.close_tab(self._debug_view, force=True)
            self._debug_view = None

    def print_message(self, browser, message, color=0, data_color=''):
        # Log the message to the debug console.
        self._debug_view.log_message(message, color, data_color)

        return True

    def _toggle_terminal_key_pressed(self, accels=None, window=None, 
            keyval=None, flags=None):
        """ _toggle_terminal_key_pressed() -> Toggle visibility of terminal
        tab box. 
        
        """

        self._browser._term_book.toggle_visible(self._debug_view)

Plugin = MessageView
# Don't auto-load this plugin.
#AUTO_LOAD = False

