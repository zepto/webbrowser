# This file is part of browser, and contains BrowserSock class for a tab 
# that communicates with the browser view over dbus.
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

""" Provides a subclass of BrowserTabBase named BrowserSock, that implements 
an external tab that uses dbus to communicate with the main browser.

"""

import os
import sys
import json
import subprocess
from optparse import OptionParser

import gtk
import glib
import gobject
import dbus
import dbus.service
import dbus.mainloop.glib
import dbus.gobject_service

from browser_classes import BrowserTabBase, BrowserBase, MSGCOLOR
from defaults import APP_NAME, MAIN_INTERFACE_NAME

class BrowserSock(BrowserTabBase):
    """ BrowserSock -> A tab that uses a socket to embed a browser.

    """

    # Define the interface used to comunicate over dbus.
    INTERFACE = "com.browser.tab%d"

    __gsignals__ = {
            'browser-plug-died' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_LONG,)),
            }

    def __init__(self, popup=False, uri=None, history_str='', 
            history_index=1, profile='default'):
        """ BrowserSock(popup=False, uri=None, history_str='', 
        history_index=1) -> A browser tab using dbus to communicate with
        the browser object.

        """

        super(BrowserSock, self).__init__(popup=popup, uri=uri, 
                history_str=history_str, history_index=history_index,
                profile=profile)

        # Define the functions to recieve data from the browser object.
        self._bus_receiver_dict = {
                'send_pid': self._receive_pid,
                'send_title': self._receive_title,
                'send_uri': self._receive_uri,
                'send_progress': self._receive_progress,
                'send_back_forward': self._receive_back_forward,
                'send_favicon_uri': self._receive_favicon_uri,
                'send_hover_uri': self._receive_hover_uri,
                'send_show_hide_download': self._receive_show_hide_download,
                'send_new_tab' : self._receive_new_tab,
                'send_download_uri': self._receive_download_uri,
                'send_embed_mime_uri' : self._receive_embed_mime_uri,
                }

        self._type = 'BrowserSock'

        self._plug_pid = None
        self._plug = None
        self._socket_id = None
        self._died = False

        # Setup the socket to embed the external browser in.
        self._socket = gtk.Socket()
        self._socket.connect('plug-removed', self._plug_removed)
        self._socket.connect('plug-added', self._plug_added)

        self.pack_start(self._socket, True)
        self.reorder_child(self._socket, 1)

        self.show_all()

    def take_focus(self):
        """ take_focus -> Take keybaord focus.

        """

        self._socket.grab_focus()

    def print_page(self):
        """ print_page -> Tells the browser to print the current page.

        """

        self._plug.print_page(self._socket_id, 
                reply_handler=lambda *args:None,
                error_handler=lambda *args:None)

    def refresh_page(self):
        """ refresh_page -> Reload the current page.

        """

        self._plug.reload(self.get_socket_id(), 
                reply_handler=lambda *args:None,
                error_handler=lambda *args:None)

    def stop_loading(self):
        """ stop_loading -> Stop the current page from loading.

        """

        if self._plug:
            self._plug.stop_loading(self.get_socket_id(), 
                    reply_handler=lambda *args:None, 
                    error_handler=lambda *args:None)

    def do_close(self):
        """ do_close -> Disconnect and close the external browser.

        """

        if self._plug:
            # First diconnect the signal handler so it doesn't try to handle
            # signals when the browser is closed.
            self._disconnect_receiver()
            try:
                ret_val = self._plug.exit(self._socket_id)
            except dbus.exceptions.DBusException as err:
                self.print_message("Error closing tab: %s" % err, MSGCOLOR)
                ret_val = True
            finally:
                self._plug = None
                return ret_val
        else:
            return False

    def _plug_access(func):
        def wrap_func(self, *args):
            try:
                retval = func(self, *args)
                return retval
            except Exception as err:
                self.print_message("Error accessing plug: %s" % err, MSGCOLOR)
                return None
        return wrap_func

    @_plug_access
    def do_zoom(self, direction):
        """ do_zoom(direction) -> Zoom in or out depending on direction.
        
        """

        self._plug.zoom(self._socket_id, direction, 
                reply_handler=lambda *args:None,
                error_handler=lambda *args:None)

    def do_highlight_toggled(self, find_string, match_case, highlight_match):
        return self._plug.set_highlight(self._socket_id, find_string, match_case, highlight_match)

    def do_set_highlight(self, find_string, match_case, highlight):
        return self._plug.set_highlight(self._socket_id, find_string, match_case, highlight)

    def do_find(self, find_string, match_case, find_direction, wrap_find):
        return self._plug.find(self._socket_id, find_string, match_case, find_direction, wrap_find)

    def do_go_to(self, uri):
        if self._plug:
            self._plug.load_uri(uri, self._socket_id, 
                    reply_handler=lambda *args:None, 
                    error_handler=lambda *args:None)
            self._page_loading = True
        else:
            self._uri=uri

    @_plug_access
    def do_get_history_length(self):
        return self._plug.get_history_length(self._socket_id)

    def do_get_back_forward_item(self, index):
        return self._plug.get_back_forward_item(self._socket_id, index)

    def do_get_history(self, index=2):
        return self._plug.get_history(self._socket_id, index)

    def do_get_current_item(self):
        return self._plug.get_current_item(self._socket_id)

    def do_get_back_item(self):
        return self._plug.get_back_item(self._socket_id)

    def do_get_forward_item(self):
        return self._plug.get_forward_item(self._socket_id)

    def do_get_history_item(self, index):
        return self._plug.get_history_item(self._socket_id, index)

    def do_go_to_history_item(self, index):
        self._plug.go_to_history_item(self._socket_id, index,
                reply_handler=lambda *args:None, 
                error_handler=lambda *args:None)

    def do_go_back(self):
        self._plug.go_back(self._socket_id, 
                reply_handler=lambda *args:None,
                error_handler=lambda *args:None)

    def do_go_forward(self):
        self._plug.go_forward(self._socket_id, 
                reply_handler=lambda *args:None,
                error_handler=lambda *args:None)

    def get_save_list(self):
        """ get_save_list() -> Get the information necessary to restore the tab
        after a crash.

        Deprecated.  Use get_save_dict instead.

        """

        return [str(self.get_pid()), json.loads(self.get_history_str())]

    def get_save_dict(self):
        """ get_save_dict() -> Get the information necessary to restore the 
        tab.

        """

        return {'pid':str(self.get_pid()), 
                'history':json.loads(self.get_history_str())}

    def get_pid(self):
        return self._plug_pid

    def get_socket_id(self):
        if not self._socket_id:
            self._socket_id = self._socket.get_id()
        return self._socket_id

    def set_pid(self, pid):
        self._connect_receiver(pid)
        self._plug_pid = pid

    def _plug_added(self, socket):
        pass
        #print(socket.window.get_children()[0].get_user_data())

    def _plug_removed(self, socket):
        self._died = True
        self._uri = ''
        self._disconnect_receiver()
        self.print_message("browsebox: plug died (pid %d) restarting" % self.get_pid(), MSGCOLOR)
        self.emit('browser-plug-died', self.get_pid())
        return True

    def _connect_receiver(self, pid):
        bus = dbus.SessionBus()
        for signal_name, handler_func in self._bus_receiver_dict.iteritems():
            bus.add_signal_receiver(handler_func, dbus_interface=BrowserSock.INTERFACE % pid, signal_name=signal_name)

    def _disconnect_receiver(self):
        bus = dbus.SessionBus()
        if self.get_pid():
            for signal_name, handler_func in self._bus_receiver_dict.iteritems():
                bus.remove_signal_receiver(handler_func, dbus_interface=BrowserSock.INTERFACE % self.get_pid(), signal_name=signal_name)

    def _receive_new_tab(self, uri, flags, socket_id):
        """ _receive_new_tab(uri, flags, socket_id) -> Open
        a new tab.  If uri is set the new tab will load uri.  Depending
        on the value of flags the new tab might share the same pid and 
        back forward history of this tab.

        """
        
        if socket_id == self._socket_id:
            def new_tab(uri, flags):
                self._new_tab(uri=uri, history_index=1, flags=flags)

            glib.idle_add(new_tab, uri, flags) 
            glib.idle_add(self.print_message, "browsebox: received a request for a new pid with uri: %s" % uri, MSGCOLOR, '38;5;180')

    def _receive_embed_mime_uri(self, mimetype, uri, handler_cmd_str, 
            socket_id):
        """ _receive_embed_mime_uri(mimetype, uri, socket_id) -> Handles 
        mimetypes that the browser can't handle.

        """

        if socket_id == self._socket_id:
            self.emit('embed-mime-uri', mimetype, uri, handler_cmd_str)

    def _receive_download_uri(self, filename, uri, socket_id):
        """ _receive_download_uri(filename, uri, socket_id) -> Add 'uri'
        to the download manager.  Use filename as the default filename in the
        download manager.

        """

        if socket_id == self._socket_id:
            self.emit('download-uri', filename, uri)

    def _receive_show_hide_download(self, socket_id):
        if socket_id == self._socket_id:
            self.emit('toggle-download-manager')

    def _receive_hover_uri(self, uri, socket_id):
        if socket_id == self._socket_id:
            self.do_receive_hover_uri(uri)

    def _receive_back_forward(self, can_go_back, can_go_forward, socket_id):
        if socket_id == self._socket_id:
            self.do_receive_back_forward(can_go_back, can_go_forward)

    def _receive_pid(self, pid):
        if pid == self.get_pid():
            self.print_message("browsebox: received my pid: %d" % long(pid), MSGCOLOR, '38;5;180')
            if self._died or not self._plug:
                self.setup_socket(pid)

    def _receive_title(self, title, socket_id):
        if socket_id == self._socket_id:
            self.do_receive_title(title)

    def _receive_uri(self, uri, socket_id):
        if socket_id == self._socket_id:
            self.do_receive_uri(uri)

    def _receive_favicon_uri(self, icon_uri, socket_id):
        if socket_id == self._socket_id:
            self.do_receive_favicon_uri(icon_uri)

    def _receive_progress(self, progress, socket_id):
        if socket_id == self._socket_id:
            self.do_receive_progress(progress)

    def setup_socket(self, pid, restart=False):
        self._plug_pid = pid
        self._died = False
        self._socket_id = self.get_socket_id()

        bus = dbus.SessionBus()
        self._plug = bus.get_object('com.browser.plug%d' % pid, '/bplug%d' % pid)

        if not self._popup:
            #try:
            self._plug.set_profile(self._profile, 
                    reply_handler=lambda *args:None, 
                    error_handler=lambda *args:None)
            self._plug.set_socket_id(self._socket_id, 
                    reply_handler=lambda *args:None, 
                    error_handler=lambda *args:None)
            #except:
                #pass

        if self._history_str:
            #try:
            self._plug.set_history(self._socket_id, self._history_str, 
                    reply_handler=lambda *args:None, 
                    error_handler=lambda *args:None)
            #except:
                #pass

        if self._uri:
            if self._history_index == 1:
                #try:
                self.load_uri(self._uri)
                #except:
                    #pass
        else:
            self._uri = 'about:blank'

class BrowserReceiver(dbus.gobject_service.ExportedGObject):

    __gsignals__ = {
            'get-socket-id' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_LONG, (gobject.TYPE_LONG,)),
            }

    def __init__(self, bus, name):
        super(BrowserReceiver, self).__init__(bus, name)

    @dbus.service.method(dbus_interface=MAIN_INTERFACE_NAME,
                        in_signature='u', out_signature='x')
    def get_socket_id(self, pid):
        return self.emit('get-socket-id', pid)

class Browser(BrowserBase):

    INTERFACE = "com.browser.main%d"

    def __init__(self, bus, uri=None, width=1213, height = 628):
        super(Browser, self).__init__(uri=uri, width=width, height=height)

        self._receiver = BrowserReceiver(bus, '/main_browser%s' % id(self))
        self._receiver.connect('get-socket-id', self._get_socket_id)

        self._died_dict = {}

        # Setup the python executable to use for external tabs.
        #self._pyexec = subprocess.Popen(['which', 'python2'], 
                #stdout=subprocess.PIPE).communicate()[0].strip()
        self._pyexec = sys.executable

        # A dictionary to match closed pids with their replacement pid.
        self._closed_pid_dict = {}

        self._connect_dbus(bus)

        if uri:
            # Open a tab if there was a uri given.
            self.do_open_tab(uri=uri)

    def _connect_dbus(self, bus):
        """ _connect_dbus(bus) -> Connect the internal dbus bus.  
        Internal dbus bus is used by external tabs to open new tabs and
        send download uri's and debug messages.

        """

        bus_receiver_dict = {
                'print_message_signal': self._receive_print_message,
                }

        for signal_name, handler_func in bus_receiver_dict.iteritems():
            bus.add_signal_receiver(handler_func, 
                    dbus_interface=Browser.INTERFACE % os.getpid(), 
                    signal_name=signal_name,
                    path='/bplug_sender%s' % id(self))

    def _clean_died_dict(self, pid):
        if pid in self._died_dict.values():
            for oldpid, newpid in self._died_dict.iteritems():
                if pid == newpid:
                    self._died_dict.pop(oldpid)
                    break

    def _receive_print_message(self, message, color, data_color):
        """ _receive_print_message(message, color, data_color) -> Log message
        to the debug console.  'color' is used to differentiate between a tabs
        message and the main windows message, and 'data_color' is for 
        different types of messages.

        """

        self.print_message(message, color, data_color)

    def _get_socket_id(self, receiver, pid):
        return self.do_open_tab(pid=pid, popup=True).get_socket_id()

    def _browser_plug_died(self, browsebox, oldpid):
        newpid = self._died_dict.get(oldpid, None)
        newpid = self.setup_plug(browsebox, pid=newpid, died=True)
        self._died_dict[oldpid] = newpid
        self._clean_died_dict(oldpid)

    def _get_pid_socket_id(self, flags, tab):
        if flags in self._shared_key_list:
            pid = tab.get_pid()
            socket_id = tab.get_socket_id()
        else:
            socket_id = None
            pid = None
        return pid, socket_id

    def do_browser_closed(self, browsebox):
        """ do_browser_closed(browsebox) -> Clean up after a tab is closed.

        """

        self._clean_died_dict(browsebox.get_pid())

    def _start_plug(self):
        tabcmd = [self._pyexec, '%s/browserplug.py' % self._path, '%s' % id(self)]
        bplug = subprocess.Popen(tabcmd)
        return bplug.pid

    def setup_plug(self, browsebox, pid=None, died=False):
        if not pid:
            pid = self._start_plug()
        elif not died:
            while True:
                try:
                    browsebox.setup_socket(pid)
                    break
                except:
                    pass
        browsebox.set_pid(pid)

    def new_tab(self, uri=None, pid=None, popup=False, history_str='', history_index=1):
        browsebox = BrowserSock(popup=popup, uri=uri, 
                history_str=history_str, history_index=history_index)

        # Connect extra signals.
        connection_dict = {
                'browser-plug-died': self._browser_plug_died,
                }
        for signal, callback in connection_dict.iteritems():
            browsebox.connect(signal, callback)

        self.do_new_tab(browsebox, uri, popup)
        self.setup_plug(browsebox, pid)

        self.print_message("main socket_id: %d" % browsebox.get_socket_id(), MSGCOLOR)

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
            pid = tab.get_pid()

        new_tab = self.new_tab(uri=uri, pid=pid, popup=popup, 
                history_str=history_str, history_index=history_index) 

        return new_tab

    def do_restore_tab(self, tab_dict, flags):
        """ do_restore_tab(tab_dict) -> Restores a tab based on 'tab_dict'.

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

        if tab_pid:
            tab_pid = int(tab_pid)
        pid = None
        new_pid = self._closed_pid_dict.get(tab_pid, None)
        for tab in self._browser_book.get_children():
            if hasattr(tab, 'get_pid'):
                if tab.get_pid() == tab_pid:
                    pid = tab_pid
                    break
                elif tab.get_pid() == new_pid:
                    pid = new_pid
                    break
        browsebox = self.do_open_tab(pid=pid, 
                history_str=history_str, flags=flags)
        if hasattr(browsebox, 'get_pid'):
            self._closed_pid_dict[tab_pid] = browsebox.get_pid()

        self._browser_book.reorder_child(browsebox, tab_index)
        self._browser_book.set_tab_state(browsebox, tab_state)

    @classmethod
    def do_create_window(cls, browsebox=None, uri=None):
        """ Create a new window.

        """

        if browsebox:
            return None

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        dbusname = dbus.service.BusName(MAIN_INTERFACE_NAME, bus)

        return Browser(bus=bus, uri=uri)

if __name__ == "__main__":
    opts = OptionParser("usage: %prog [options]")
    opts.add_option("-u", "--uri", action="store", type="string", dest="uri", help="Load uri")

    options, args = opts.parse_args()
    if args:
        opts.print_help()
        exit(1)

    Browser.do_create_window(uri=options.uri).run()
