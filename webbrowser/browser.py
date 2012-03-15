# This file is part of browser, and contains the main application class.
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

""" A web browser using webkit.  

This browser has two different types of tabs, internal tabs that are part of 
the main application, and external tabs that are separate applications 
embedded in a tab using gtk sockets.  External tabs can have multiple tabs that
share on external application, or they can each be separate applications.

"""

import os
import sys
import json
import subprocess
from optparse import OptionParser

import gtk
import dbus
import dbus.service
import dbus.mainloop.glib
import dbus.gobject_service

from browser_classes import BrowserBase, ProfileManager, MSGCOLOR
from browser_dbus import BrowserSock
from browser_dbus import BrowserReceiver
from browser_nodbus import BrowserTab
from defaults import APP_NAME, MAIN_INTERFACE_NAME

class Browser(BrowserBase):
    """ Main browser handles starting and exiting and opening and closing
    tabs.  It also handles the downloads, debug terminal, and bookmarks.

    """

    # Make a global of the dbus interface name used to open new tabs
    INTERFACE = "com.browser.main%d"

    def __init__(self, bus=None, uri=None, profile='default', width=1213, 
            height=628):
        """ Browser(bus=None, uri=None, profile='default', width=1213, 
        height=628) -> 
        Main browser window of size 'width'x'height' embed browser tab 'pid'
        and use dbus 'bus' to communicate with the external tabs.

        """

        super(Browser, self).__init__(uri=uri, profile=profile, width=width, 
                height=height)

        # Connect the dbus receiver to allow opening new tabs from external
        # tabs.
        if bus:
            self._receiver = BrowserReceiver(bus, '/main_browser%s' % id(self))
            self._receiver.connect('get-socket-id', self._get_socket_id)

            # Connect dbus to bus.
            self._connect_dbus(bus)
            self._bus = bus

        # Should we use a proxy.
        self._no_proxy = True
        self._proxy = os.environ.get('http_proxy', '')
        os.environ['http_proxy'] = ''

        # This dictionary is used to keep track of which tabs have died
        # so it can restart connected tabs properly.
        self._died_dict = {}

        # A dictionary to match closed pids with their replacement pid.
        self._closed_pid_dict = {}

        # Add an extra keyboard shortcut to open alternative tabs
        keyval, modifier = gtk.accelerator_parse('<Control><Alt>t')
        self._accels.connect_group(keyval, modifier, gtk.ACCEL_VISIBLE, 
                self._new_tab_key_pressed)
        keyval, modifier = gtk.accelerator_parse('<Control><Shift><Alt>t')
        self._accels.connect_group(keyval, modifier, gtk.ACCEL_VISIBLE, 
                self._new_tab_key_pressed)
        keyval, modifier = gtk.accelerator_parse('<Control><Mod4>t')
        self._accels.connect_group(keyval, modifier, gtk.ACCEL_VISIBLE, 
                self._new_tab_key_pressed)
        
        # Setup the python executable to use for external tabs.
        #self._pyexec = subprocess.Popen(['which', 'python2'], 
                #stdout=subprocess.PIPE).communicate()[0].strip()
        self._pyexec = sys.executable

        if uri:
            # Open a tab if there was a uri given.
            self.do_open_tab(uri=uri)

        #self._window.set_colormap(self._window.get_screen().get_rgba_colormap())
    
    def _connect_dbus(self, bus, disconnect=False):
        """ _connect_dbus(bus, disconnect=False) -> Connect the internal 
        dbus bus.  Internal dbus bus is used by external tabs to send debug 
        messages.

        """

        bus_receiver_dict = {
                'print_message_signal': self._receive_print_message,
                }

        for signal_name, handler_func in bus_receiver_dict.iteritems():
            if disconnect:
                bus.remove_signal_receiver(handler_func, 
                        dbus_interface=Browser.INTERFACE % os.getpid(), 
                        signal_name=signal_name,
                        path='/bplug_sender%s' % id(self))
            else:
                bus.add_signal_receiver(handler_func, 
                        dbus_interface=Browser.INTERFACE % os.getpid(), 
                        signal_name=signal_name,
                        path='/bplug_sender%s' % id(self))

    def _clean_died_dict(self, pid):
        """ _clean_died_dict(pid) -> Clean the dictionary of dead tabs of
        tab pid.  If a tab dies its old and new pids are stored in the 
        died_dict.  This function cleans already restarted tabs out of
        that dictionary.

        """

        if pid in self._died_dict.values():
            # The pid has died.
            for oldpid, newpid in self._died_dict.iteritems():
                if pid == newpid:
                    # When pid == newpid than oldpid should be removed
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
        """ _get_socket_id(receiver, pid) -> Open a new tab for the external 
        tab with a pid of 'pid'.  This function returns the socket id of the 
        new tab's socket.
        
        """

        # Just send a normal tab.
        return self.do_open_tab(pid=pid, popup=True, 
                tab=BrowserSock()).get_socket_id()
            
    def _browser_plug_died(self, browsebox, oldpid):
        """ _browser_plug_died(browsebox, oldpid) -> When an external tab's
        browser dies this function is called to start a new one.  The old
        pid is associated with the new pid in the died_dict so any tabs that
        share the same pid can be restarted properly.

        """

        newpid = self._died_dict.get(oldpid, None)
        newpid = self.setup_plug(browsebox, pid=newpid, died=True)
        self._died_dict[oldpid] = newpid
        self._clean_died_dict(oldpid)

    def do_browser_closed(self, browsebox):
        """ do_browser_closed(browsebox) -> Clean up after a tab is closed.

        """

        if type(browsebox) == BrowserSock:
            self._clean_died_dict(browsebox.get_pid())
        else:
            self.print_message("main: tab closed", MSGCOLOR)

    def new_tab(self, uri=None, popup=False, history_str='', history_index=1):
        """ new_tab(uri=None, popup=False, history_str='', history_index=1) 
        -> Open a new internal tab.  Load uri in the new tab and if popup is 
        True and uri is empty open the tab in the foreground.  history_index 
        is the index in the history to load when the tab opens.  history_str 
        is a string containing the history to copy to the new tab.

        """

        browsebox = BrowserTab(popup=popup, uri=uri, 
                history_str=history_str, history_index=history_index,
                profile=self._profile)

        self.do_new_tab(browsebox, uri, popup)

        self.print_message("main: tab added", MSGCOLOR)

        return browsebox

    def _start_plug(self):
        """ _start_plug() -> Start external browser to embed in a tab.
        Returns the pid of the new process.

        """

        tabcmd = [self._pyexec, '%s/browserplug.py' % self._path, '%s' % id(self)]
        env_dict = os.environ
        if not self._no_proxy:
            env_dict['http_proxy'] = self._proxy
            self._no_proxy = True
        bplug = subprocess.Popen(tabcmd, env=env_dict)
        env_dict['http_proxy'] = ''

        return bplug.pid

    def setup_plug(self, browsebox, pid=None, died=False):
        """ setup_plug(browsebox, pid=None, died=False) -> Setup a plug to
        embed in a tab.  If the pid is set then the plug is started and it
        just needs to start a new browser instance to embed.  Otherwise start
        a new plug.

        """

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

        return pid

    def new_tab_plug(self, uri=None, pid=None, popup=False, history_str='', 
            history_index=1):
        """ new_tab_plug(uri=None, pid=None, popup=False, history_str='', 
        history_index=1) -> Start a new  external tab.  Open a shared tab if 
        pid is set. If set, load history item of index 'history_index' or uri 
        if set.  history_str is a string containing the history to copy to 
        the new tab.

        """

        browsebox = BrowserSock(popup=popup, uri=uri, 
                history_str=history_str, history_index=history_index,
                profile=self._profile)
        
        # Connect extra signals.
        connection_dict = {
                'browser-plug-died': self._browser_plug_died,
                }
        for signal, callback in connection_dict.iteritems():
            browsebox.connect(signal, callback)

        self.do_new_tab(browsebox, uri, popup)
        self.setup_plug(browsebox, pid)

        self.print_message("main socket_id: %d" % browsebox.get_socket_id(), 
                MSGCOLOR)

        return browsebox

    def do_open_tab(self, flags=0, tab=None, uri=None, popup=False, 
            pid=None, history_str='', history_index=1, button=None,
            tab_type=None):
        """ do_open_tab(flags=0, tab=None, uri=None, popup=False, 
        pid=None, history_str='', history_index=1 tab_type=None) ->
        Open a new tab.  If flags indecates that alt was held than a tab
        of a different type than tab will be opened.  Load uri in the new tab
        or history item history_index.

        """

        if button == 2:
            # Get selected text (primary clipboard)
            clipboard = gtk.clipboard_get(selection='PRIMARY')
            clipboard_text = clipboard.wait_for_text()

            # Load selection
            if clipboard_text:
                # Load selected text in address entry
                uri = clipboard_text

        if not tab and not tab_type:
            tab = self._current_tab

        if not gtk.gdk.SHIFT_MASK & flags:
            # The new tab is only going to have back history.
            history_index = 1
        else:
            # If shift was held down, and 'history_str' is not set, than 
            # copy the history of 'tab' into the new tab.
            if not history_str:
                if tab:
                    history_str = tab.do_get_history(history_index)
                else:
                    history_str = self._current_tab.do_get_history(history_index)
            if hasattr(tab, 'get_pid'):
                pid = tab.get_pid()
            elif hasattr(self._current_tab, 'get_pid'):
                pid = self._current_tab.get_pid()

        if type(tab) == BrowserSock or tab_type == 'BrowserSock':
            if gtk.gdk.MOD1_MASK & flags:
                # Open an internal tab because the alt key was pressed
                new_tab = self.new_tab(uri=uri, popup=popup, 
                        history_str=history_str, history_index=history_index) 
            else:
                if gtk.gdk.MOD4_MASK & flags:
                    self._no_proxy = False
                new_tab = self.new_tab_plug(uri=uri, pid=pid, popup=popup, 
                        history_str=history_str, history_index=history_index) 
        else:
            if gtk.gdk.MOD1_MASK & flags or gtk.gdk.MOD4_MASK & flags:
                if gtk.gdk.MOD4_MASK & flags:
                    self._no_proxy = False
                # Open an external tab because the alt key was pressed
                new_tab = self.new_tab_plug(uri=uri, popup=popup, 
                        history_str=history_str, history_index=history_index)
            else:
                new_tab = self.new_tab(uri=uri, popup=popup, 
                        history_str=history_str, history_index=history_index)

        return new_tab

    def do_restore_tab(self, tab_dict, flags):
        """ do_restore_tab(tab_dict, flags) -> Restores a tab based on 
        'tab_dict'.  'flags' holds the key masks of the modifier keys that 
        were pressed.

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
            pid = None
            tab_pid = int(tab_pid)
            new_pid = self._closed_pid_dict.get(tab_pid, None)
            for tab in self._browser_book.get_children():
                if hasattr(tab, 'get_pid'):
                    if tab.get_pid() == tab_pid:
                        pid = tab_pid
                        break
                    elif tab.get_pid() == new_pid:
                        pid = new_pid
                        break
            browsebox = self.do_open_tab(tab_type='BrowserSock', pid=pid, 
                    history_str=history_str, flags=flags)
            if hasattr(browsebox, 'get_pid'):
                self._closed_pid_dict[tab_pid] = browsebox.get_pid()
        else:
            browsebox = self.do_open_tab(tab_type='BrowserTab', flags=flags, 
                    history_str=history_str)

        self._browser_book.reorder_child(browsebox, tab_index)
        self._browser_book.set_tab_state(browsebox, tab_state)

    def do_exit(self):
        """ Disconnect dbus handlers.
        
        """

        self._connect_dbus(self._bus, disconnect=True)

    def do_create_window(self, browsebox=None, uri=None):
        """ Create a new window.

        """

        if browsebox:
            if browsebox.type == 'BrowserSock':
                return None

        return create_window(self._bus, uri=uri)

def create_window(bus, uri=None, profile='default'):
    """ Create a new window.

    """

    return Browser(bus=bus, uri=uri, profile=profile)

def load_uri(uri):
    """ load_uri(uri) -> Load uri in new tab.

    """

    window = tuple(Browser.window_set)[-1]
    window.new_tab(uri=uri)

def get_options():
    """ Get the command line arguments.

    """

    opts = OptionParser("usage: %prog [options] [Address/Search Phrase]")
    opts.add_option("-u", "--uri", action="store", type="string", dest="uri", 
            default='', help="Load uri")
    opts.add_option("-p", "--profile", action="store", type="string", dest="profile", 
            default='default', help="Set profile")

    options, args = opts.parse_args()
    if args and not options.uri:
        options.uri = ' '.join(args)

    return options

if __name__ == "__main__":
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    main_bus = dbus.SessionBus()
    main_bus_name = dbus.service.BusName(MAIN_INTERFACE_NAME, main_bus)

    profile_bus = dbus.SessionBus()
    profile_bus_name = dbus.service.BusName('com.browser.main', profile_bus)

    options = get_options()

    with ProfileManager(profile_bus, options.__dict__, load_uri) as profile:
        if profile._pid_file:
            create_window(main_bus, uri=options.uri, 
                    profile=options.profile).run()
