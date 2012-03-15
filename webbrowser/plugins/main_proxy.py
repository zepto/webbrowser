# This file is part of browser.  This is an example plugin.
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

""" Change the proxy.

"""

import os

import gtk
import gobject
import glib

from plugin_loader import PluginBase

class ProxyEdit(gtk.Alignment):
    """ PluginList -> A list of plugins.

    """

    __gsignals__ = {
            'proxy-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING,)),
            }

    def __init__(self, halign=0.5, valign=0.5, hstretch=1, vstretch=1, cur_proxy=''):
        super(ProxyEdit, self).__init__(halign, valign, hstretch, vstretch)

        self._title = 'Proxy'

        self._icon = gtk.Image()
        self.set_icon('web-browser')

        self.add(self._setup_controls())

        self._proxy_entry.grab_focus()
        self._proxy_entry.set_text(cur_proxy)

    def _setup_controls(self):
        vbox = gtk.VBox(homogeneous=False, spacing=12)

        proxy_frame = self._make_frame('<b>Proxy:</b>')

        proxy_align = gtk.Alignment(0.5, 0.5, 1, 0)
        proxy_align.set_padding(0, 0, 12, 0)

        self._proxy_entry = gtk.Entry()
        self._proxy_entry.set_icon_from_icon_name(1, 'gtk-clear')
        self._proxy_entry.connect('activate', self._proxy_button_clicked) 
        self._proxy_entry.connect('icon-release', self._proxy_entry_icon_release)

        self._proxy_button = gtk.Button('gtk-ok')
        self._proxy_button.set_use_stock(True)
        self._proxy_button.connect('clicked', self._proxy_button_clicked) 

        proxy_button_hbox = gtk.HBox(homogeneous=False, spacing=6)

        proxy_hbox = gtk.HBox(homogeneous=False, spacing=6)
        proxy_hbox.pack_start(self._proxy_entry, True, True)
        proxy_hbox.pack_start(self._proxy_button, False, False)
        proxy_align.add(proxy_hbox)
        proxy_frame.add(proxy_align)

        proxy_frame_align = gtk.Alignment(0.5, 0, 1, 0)
        proxy_frame_align.add(proxy_frame)

        vbox.pack_start(proxy_frame_align, False, False)

        return vbox

    def _make_frame(self, label_text):
        frame_label = gtk.Label(label_text)
        frame_label.set_use_markup(True)
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_NONE)
        frame.set_label_widget(frame_label)

        return frame

    def _proxy_entry_icon_release(self, proxy_entry, position, event):
        if position == gtk.ENTRY_ICON_SECONDARY:
            proxy_entry.set_text('')

    def _proxy_button_clicked(self, proxy_button):
        self.emit('proxy-changed', self._proxy_entry.get_text())

    def set_icon(self, icon_name):
        """ set_icon(icon_name) -> Set the icon from icon_name.

        """

        self._icon.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)

    def get_icon(self):
        """ get_icon() -> Return the icon.

        """

        return self._icon


    def get_title(self):
        """ get_title -> Return the title.

        """

        return self._title

    def close(self):
        """ close -> Return False otherwise TabBase will close it.

        """

        return False

class Proxy(PluginBase):
    """ Plugin class

    """

    def __init__(self, browser):
        """ Plugin

        """

        super(Proxy, self).__init__(browser)

    def run(self):
        self._proxy = ProxyEdit(cur_proxy=self._browser._proxy)
        self._proxy.show_all()
        self._browser._term_book.new_tab(self._proxy, True)

        # Connect to the proxy signals.
        plugin_connect_dict = {
                'proxy-changed':(self._proxy_changed,),
                }
        for signal, handler_tup in plugin_connect_dict.iteritems():
            self._proxy.connect(signal, *handler_tup)

    def exit(self):
        self._browser._term_book.close_tab(self._proxy, force=True)
        self._proxy = None

    def _proxy_changed(self, proxyedit, proxy_str):
        """ Change the proxy to proxy_str

        """

        self._browser._proxy = proxy_str

Plugin = Proxy
