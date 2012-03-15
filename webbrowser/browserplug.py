# This file is part of browser, and contains the base classes for embeding a 
# browser view in a socket and communicating with the main browser window 
# over dbus.
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

""" Classes for embeding a browser view in a gtk plug and communicating
with the main window over dbus.

"""

import warnings
import os
from sys import argv

import gtk
import gobject

import dbus
import dbus.service
import dbus.gobject_service
import dbus.mainloop.glib

from browserplug_classes import BrowserView, MSGCOLOR
from functions import redirect_warnings, print_message
from defaults import PLUG_INTERFACE_NAME

class PlugBrowser(BrowserView):
    """ A browser class to put in a gtk plug.

    """
    
    def __init__(self, socket_id, profile):
        """ PlugBrowser(socket_id, profile) -> Basic initialization and 
        setup of a gtk.Plug to hold this browser view.

        """

        super(PlugBrowser, self,).__init__(profile)

        self._socket_id = socket_id

        self._pid = os.getpid()

        plug = gtk.Plug(socket_id)
        plug.add(self)
        plug.show_all()

    def do_close(self):
        """ do_close -> Do some basic cleanup.

        """

        self.destroy()

        return True

    def get_pid(self):
        """ get_pid -> Return the pid of this browser view.
        Not really used anymore.

        """

        return self._pid

    def get_socket_id(self):
        """ get_socket_id -> Return the id of the socket this browser view 
        is embeded in.

        """
        return self._socket_id

class PlugSender(dbus.gobject_service.ExportedGObject):
    """ A dbus gobject used to send messages across dbus to the main window.

    To differentiate between tabs the socket id of the socket containing each
    browser view is sent with every message sent to a tab.  Also this 
    processes pid used in the interface to the tab so separate browser windows
    will not listen to messages to another.

    To send messages to the main window the parent processes pid is used.

    """

    # Define the interfaces used to communicate with the tabs and main window.
    TAB_INTERFACE = 'com.browser.tab%d' % os.getpid()
    MAIN_INTERFACE = 'com.browser.main%d' % os.getppid()

    def __init__(self, bus, object_path):
        """ PlugSender(bus, object_path) -> Setup the dbus bus to communicate
        with the tabs and the main window.

        """

        super(PlugSender, self).__init__(bus, object_path)
        self._pid = os.getpid()

    def _showwarning(self, message, category, filename, lineno, file=None, 
            line=None):
        """ _showwarning(message, category, filename, lineno, file=None, 
                line=None) -> 
        Override the default showwarning function to redirect warning output to
        the debug terminal. 
        
        """

        warning_str = 'warning: %s (%s): %s' % (os.path.basename(filename), 
                lineno, message)
        self.print_message(warning_str, MSGCOLOR, '38;5;96')

    def print_message(self, message, color=0, data_color=''): 
        """ print_message(message, color=0, data_color='') -> Print messages
        to the debug terminal. 
        
        """

        self.print_message_signal('browserplug %d: %s' % 
                (self._pid, message), color, data_color)

    @dbus.service.signal(dbus_interface=MAIN_INTERFACE,signature='sus')
    def print_message_signal(self, message, color, data_color): 
        """ print_message_signal(message, color=0, data_color='') -> Sends the
        message to the main window.
        
        """

        pass

    @dbus.service.signal(dbus_interface=TAB_INTERFACE)
    def send_new_tab(self, uri, flags, socket_id):
        """ send_new_tab(uri, flags, socket_id) -> Send a request for a new
        tab.  

        'uri' is the uri to open in the new tab.
        'flags' are the keyboard modifier flags set when the new tab
                was requested.  The main window should use them to determine
                what kind of tab to open and how to open it.

        """

        self.print_message( "sending uri: %s" % uri, MSGCOLOR, '38;5;64')

    @dbus.service.signal(dbus_interface=TAB_INTERFACE,signature='ssu')
    def send_download_uri(self, filename, uri, socket_id):
        """ send_download_uri(filename, uri, socket_id) -> Send a uri and 
        filename to be added to the download manager.

        """

        self.print_message("sending download: %s" % uri, MSGCOLOR, '38;5;56')

    @dbus.service.signal(dbus_interface=TAB_INTERFACE,signature='sssu')
    def send_embed_mime_uri(self, mimetype, uri, handler_cmd_str, socket_id):
        """ send_embed_mime_uri(mimetype, uri, handler_cmd_str, socket_id) ->
        Send a mimetype, uri, and the command to open the uri with.

        """

        self.print_message(
                "sending mime-type (%s) handled by command %s and uri to embed: %s" % 
                (mimetype, handler_cmd_str, uri), MSGCOLOR, '38;5;56')

    @dbus.service.signal(dbus_interface=TAB_INTERFACE,signature='bbu')
    def send_back_forward(self, can_go_back, can_go_forward, socket_id):
        """ send_back_forward(can_go_back, can_go_forward, socket_id) ->
        Notify the tab whether there is back and/or forward history.

        """

        pass

    @dbus.service.signal(dbus_interface=TAB_INTERFACE,signature='su')
    def send_hover_uri(self, uri, socket_id):
        """ send_hover_uri(uri, socket_id) -> Send the uri that the mouse
        is hovering over.

        """

        pass

    @dbus.service.signal(dbus_interface=TAB_INTERFACE,signature='su')
    def send_favicon_uri(self, uri, socket_id):
        """ send_favicon_uri(uri, socket_id) -> Send the favicon uri to the 
        tab.

        """

        self.print_message( "sending favicon uri: %s" % uri, MSGCOLOR, 
                '38;5;138')

    @dbus.service.signal(dbus_interface=TAB_INTERFACE,signature='du')
    def send_progress(self, progress, socket_id):
        """ send_progress(progress, socket_id) -> Send the loading progress
        to the tab.

        """

        pass

    @dbus.service.signal(dbus_interface=TAB_INTERFACE,signature='su')
    def send_uri(self, uri, socket_id):
        """ send_uri(uri, socket_id) -> Send 'uri' to the tab.

        """

        self.print_message( "sending uri: %s (pid: %d, socket_id: %d)" % 
                (uri, self._pid, socket_id), MSGCOLOR, '38;5;175')

    @dbus.service.signal(dbus_interface=TAB_INTERFACE,signature='su')
    def send_title(self, title, socket_id):
        """ send_title(title, socket_id) -> Send 'title' to the tab.

        """

        self.print_message( "sending title: %s (pid: %d, socket_id: %d)" % 
                (title, self._pid, socket_id), MSGCOLOR, '38;5;178')

    @dbus.service.signal(dbus_interface=TAB_INTERFACE,signature='u')
    def send_pid(self, pid):
        """ send_pid(pid) -> Send 'pid' to the tab so it knows that this
        process and webview are ready.

        """

        self.print_message( "sending pid: %d" % pid, MSGCOLOR)

    @dbus.service.signal(dbus_interface=TAB_INTERFACE)
    def send_show_hide_download(self, socket_id):
        """ send_show_hide_download(socket_id) -> Ask the browser to toggle
        the visibility of the download manager.

        """

        pass

class PlugReceiver(dbus.gobject_service.ExportedGObject):
    """ A dbus gobject for relaying messages from the browser or tab to the
    main signal handler of this process.

    """

    # Define all the custom signals available to emit from this object.
    __gsignals__ = {
            'print-page' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_LONG,)),
            'set-highlight' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_LONG, gobject.TYPE_STRING, 
                    gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN)),
            'find' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_BOOLEAN, 
                (gobject.TYPE_LONG, gobject.TYPE_STRING, 
                    gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN, 
                    gobject.TYPE_BOOLEAN)),
            'get-load-status' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_LONG, 
                (gobject.TYPE_LONG,)),
            'get-current-history-index' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_LONG, (gobject.TYPE_LONG,)),
            'go-to-history-item' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_LONG, gobject.TYPE_STRING)),
            'get-history-length' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, (gobject.TYPE_LONG,)),
            'get-back-forward-item' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, (gobject.TYPE_LONG, gobject.TYPE_LONG)),
            'get-history-item' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, (gobject.TYPE_LONG, gobject.TYPE_LONG)),
            'get-current-item' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, (gobject.TYPE_LONG,)),
            'get-back-item' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, (gobject.TYPE_LONG,)),
            'get-forward-item' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, (gobject.TYPE_LONG,)),
            'get-uri' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_STRING, 
                (gobject.TYPE_LONG,)),
            'get-history' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_STRING, 
                (gobject.TYPE_LONG, gobject.TYPE_LONG)),
            'can-go-forward' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_BOOLEAN, (gobject.TYPE_LONG,)),
            'can-go-back' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_BOOLEAN, 
                (gobject.TYPE_LONG,)),
            'stop-loading' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_LONG,)),
            'reload' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_LONG,)),
            'load-uri' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_STRING, 
                (gobject.TYPE_STRING, gobject.TYPE_LONG)),
            'go-back' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_LONG,)),
            'go-forward' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_LONG,)),
            'zoom' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_LONG, gobject.TYPE_LONG)),
            'set-socket-id' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_LONG,)),
            'set-history' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_LONG, gobject.TYPE_STRING)),
            'exit' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_BOOLEAN, 
                    (gobject.TYPE_LONG,)),
            }

    def __init__(self, bus, object_path):
        """ PlugReciever -> Receives messages over dbus from the tab or 
        browser and emits them as gobject signals to the main signal handler.

        """

        super(PlugReceiver, self).__init__(bus, object_path)
        self.profile = 'default'
    
    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, in_signature='s')
    def set_profile(self, profile):
        """ set_profile -> Set the profile to use.

        """

        self.profile = profile

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, in_signature='u')
    def print_page(self, socket_id):
        """ print_page -> Tell the main signal handler that the browser wants
        to print the page.

        """

        self.emit('print-page', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='usbb')
    def set_highlight(self, socket_id, find_string, case_sensitive, highlight):
        """ set_highlight(socker_id, find_string, case_sensitive, highlight) 
        -> Enable or disable highlight of search strings on the page, and 
        return whatever the result was.

        """

        return self.emit('set-highlight', socket_id, find_string, 
                case_sensitive, highlight)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='usbbb', out_signature='b')
    def find(self, socket_id, find_string, case_sensitive=False, 
            forward=True, wrap=True):
        """ find(socket_id, find_string, case_sensitive=False, forward=True, 
        wrap=True) -> Find the find_string on the page given the requirements
        specified by the function arguments, and return the number found.

        """

        return self.emit('find', socket_id, find_string, case_sensitive, 
                forward, wrap)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='u', out_signature='u')
    def get_load_status(self, socket_id):
        """ get_load_status -> Return the load status.

        Not used.

        """

        return self.emit('get-load-status', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='u', out_signature='x')
    def get_current_history_index(self, socket_id):
        """ get_current_history_index -> Return the index in the back forward
        history of the current page.

        """

        return self.emit('get-current-history-index', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, in_signature='us')
    def go_to_history_item(self, socket_id, index):
        """ go_to_history_item(socket_id, index) -> Go to the item at 'index'
        in the back forward history.

        """

        self.emit('go-to-history-item', socket_id, index)
    
    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='u', out_signature='xx')
    def get_history_length(self, socket_id):
        """ get_history_length -> Return a tuple of the back history length
        and the forward history length.

        """

        return self.emit('get-history-length', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='ux', out_signature='ss')
    def get_back_forward_item(self, socket_id, index):
        """ get_back_forward_item(socket_id, index) -> Return the title and
        uri of the item indexed by 'index' in the back forward history.

        """

        return self.emit('get-back-forward-item', socket_id, index)
    
    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='ux', out_signature='sx')
    def get_history_item(self, socket_id, index):
        """ get_history_item(socket_id, index) -> Return the uri and index 
        of the item at 'index' in the back forward history.
        
        """

        return self.emit('get-history-item', socket_id, index)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='u', out_signature='sx')
    def get_current_item(self, socket_id):
        """ get_current_item(socket_id) -> Return the uri and index of the
        current page.

        """

        return self.emit('get-current-item', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='u', out_signature='sx')
    def get_back_item(self, socket_id):
        """ get_back_item(socket_id) -> Return the uri and index of the 
        previous item in history.

        """

        return self.emit('get-back-item', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='u', out_signature='sx')
    def get_forward_item(self, socket_id):
        """ get_forward_item(socket_id) -> Return the uri and index of the 
        next item in history.

        """

        return self.emit('get-forward-item', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='u', out_signature='s')
    def get_uri(self, socket_id):
        """ get_uri(socket_id) -> Return the current uri.

        """

        return self.emit('get-uri', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='ux', out_signature='s')
    def get_history(self, socket_id, index=2):
        """ get_history(socket_id, index=2) -> Return a json dumped string
        of the history.  'index' is used to override the current history 
        index should be.

        """

        return self.emit('get-history', socket_id, index)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='u', out_signature='b')
    def can_go_forward(self, socket_id):
        """ can_go_forward -> Return True or False depending on whether the
        browser has forward history or not.

        """

        return self.emit('can-go-forward', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, 
            in_signature='u', out_signature='b')
    def can_go_back(self, socket_id):
        """ can_go_back -> Return True or False depending on whether the 
        browser has back history or not.

        """

        return self.emit('can-go-back', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, in_signature='u')
    def stop_loading(self, socket_id):
        """ stop_loading -> Stop loading the current page.

        """

        self.emit('stop-loading', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, in_signature='u')
    def reload(self, socket_id):
        """ reload -> Refresh the current page.

        """

        self.emit('reload', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME,
                        in_signature='su', out_signature='s')
    def load_uri(self, uri, socket_id):
        """ load_uri(uri, socket_id) -> Load 'uri' in the brorwser.

        """

        return self.emit('load-uri', uri, socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, in_signature='u')
    def go_back(self, socket_id):
        """ go_back -> Go one step back in history.

        """

        self.emit('go-back', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, in_signature='u')
    def go_forward(self, socket_id):
        """ go_forward -> Jump on step forward in history.

        """

        self.emit('go-forward', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, in_signature='uu')
    def zoom(self, socket_id, direction):
        """ zoom -> Zoom in or out.

        """

        self.emit('zoom', socket_id, direction)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME,
                        in_signature='xs')
    def set_history(self, socket_id, history_str):
        """ set_history(socket_id, history_str) -> Set the history of the
        browser to history_str.

        """

        self.emit('set-history', socket_id, history_str)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME,
                        in_signature='x')
    def set_socket_id(self, socket_id):
        """ set_socket_id -> Set the socket id of the new browser view to
        socket_id.

        """

        self.emit('set-socket-id', socket_id)

    @dbus.service.method(dbus_interface=PLUG_INTERFACE_NAME, out_signature='b')
    def exit(self, socket_id):
        """ exit -> Close the tab.

        """

        return self.emit('exit', socket_id)

class PlugMain(object):
    """ The main signal handler for the browser plug.

    """

    def __init__(self, bus, main_path=''):
        """ PlugMain(bus) -> Setup the sender and receiver of dbus messages,
        and open and close tab plugs.

        """

        self._main_path = '/main_browser%s' % main_path

        self._pid = os.getpid()
        self._plug_dict = {}
        self._plug_connect_dict = {
            'new-tab' : self.plug_new_tab,
            'message' : self.plug_message,
            'hover-uri' : self.plug_hover_uri,
            'favicon-uri' : self.plug_favicon_uri,
            'new-browser' : self.plug_new_browser,
            'uri-changed' : self.plug_uri_changed,
            'back-forward' : self.plug_back_forward,
            'download-uri' : self.plug_download_uri,
            'title-changed' : self.plug_title_changed,
            'embed-mime-uri' : self.plug_embed_mime_uri,
            'progress-changed' : self.plug_progress_changed,
            'show-hide-download' : self.plug_show_hide_download,
            }

        # Setup and connect the receiver.
        self._receiver = PlugReceiver(bus, '/bplug%d' % self._pid)
        self._connect_receiver()

        # Setup the message sender.
        self._sender = PlugSender(dbus.SessionBus(), 
                '/bplug_sender%s' % main_path)
        self._sender.send_pid(self._pid)

    def run(self):
        """ run -> Start a new gtk main loop.

        """

        gobject.threads_init()

        with redirect_warnings(self._sender._showwarning):
            gtk.main()

    def _connect_receiver(self):
        """ _connect_receiver -> Connect signal handlers to the signals
        emitted by the message receiver.

        """

        connect_dict = {
                'zoom' : self.zoom,
                'find' : self.find,
                'exit' : self.exit,
                'reload' : self.reload,
                'get-uri' : self.get_uri,
                'go-back' : self.go_back,
                'load-uri' : self.load_uri,
                'go-forward' : self.go_forward,
                'print-page' : self.print_page,
                'set-history' : self.set_history,
                'can-go-back' : self.can_go_back,
                'get-history' : self.get_history,
                'stop-loading' : self.stop_loading,
                'set-socket-id' : self.set_socket_id,
                'get-back-item' : self.get_back_item,
                'set-highlight' : self.set_highlight,
                'can-go-forward' : self.can_go_forward,
                'get-load-status' : self.get_load_status,
                'get-history-item' : self.get_history_item,
                'get-current-item' : self.get_current_item,
                'get-forward-item' : self.get_forward_item,
                'get-history-length' : self.get_history_length,
                'go-to-history-item' : self.go_to_history_item,
                'get-back-forward-item' : self.get_back_forward_item,
                'get-current-history-index' : self.get_current_history_index,
                }

        for signal, callback in connect_dict.iteritems():
            self._receiver.connect(signal, callback)

    def _connect_plug(self, browser_plug):
        """ _connect_plug(browser_plug) -> Connect the signals to the
        signal handlers for the browser plug.

        """

        for signal, callback in self._plug_connect_dict.iteritems():
            browser_plug.connect(signal, callback)

    def get_plug(self, socket_id):
        """ get_plug(socket_id) -> Return the browser plug embedded in the
        socket with the socket id 'socket_id', create a new one of none was
        found.

        """

        browser_plug = self._plug_dict.get(socket_id, None)

        # Add a new browser plug if there one was not found.
        if not browser_plug:
            browser_plug = self._add_plug(socket_id)
        return browser_plug

    def _add_plug(self, socket_id):
        """ _add_plug(socket_id) -> Create and return a browser plug.

        """

        browser_plug = PlugBrowser(socket_id, self._receiver.profile)
        self._plug_dict[socket_id] = browser_plug
        return browser_plug

    ######################
    # Receiver callbacks #
    ######################
    def exit(self, receiver, socket_id):
        """ exit(receiver, socket_id) -> Close the browser plug connected to
        the socket 'socket_id' and clean up the plug dict.

        If the last plug was closed exit this process

        """

        browser_plug = self._plug_dict.pop(socket_id, None)
        if self._plug_dict:
            if browser_plug:
                self._sender.print_message("removing socket (%d)" % 
                        socket_id, MSGCOLOR)
                return browser_plug.close()
            else:
                return False
        else:
            self._sender.print_message("exiting...", MSGCOLOR)
            print_message("browserplug %d: exiting..." % self._pid, MSGCOLOR)
            gtk.main_quit()
            return browser_plug.close()

    def print_page(self, receiver, socket_id):
        """ print_page(receiver, socket_id) -> Tell the browser plug at
        'socket_id' to print its page.

        """

        browser_plug = self.get_plug(socket_id)
        browser_plug.print_page()

    def set_highlight(self, receiver, socket_id, find_string, 
            case_sensitive, highlight):
        """ set_highlight -> Relay the function arguments to the browser 
        plug at 'socket_id.'

        """

        browser_plug = self.get_plug(socket_id)
        browser_plug.set_highlight(find_string, case_sensitive, highlight)

    def find(self, receiver, socket_id, find_string, case_sensitive=False, 
            forward=True, wrap=True):
        """ find -> Send the function arguments to the plug at 'socket_id', 
        and return the result.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.find(find_string, case_sensitive, forward, wrap)

    def get_load_status(self, receiver, socket_id):
        """ get_load_status(receiver, socket_id) -> Return the load status.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.get_load_status()

    def get_current_history_index(self, receiver, socket_id):
        """ get_current_history_index(receiver, socket_id) -> Ask the plug
        at 'socket_id' for the index of the current page, and return the
        result.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.get_current_history_index()

    def go_to_history_item(self, receiver, socket_id, index):
        """ go_to_history_item(receiver, socket_id, index) -> Ask the
        plug to go to history item 'index.'

        """

        browser_plug = self.get_plug(socket_id)
        browser_plug.go_to_history_item(index)
    
    def get_history_length(self, receiver, socket_id):
        """ get_history_length(receiver, socket_id) -> Ask for the length of
        the back forward history and return the result.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.get_history_length()

    def get_back_forward_item(self, receiver, socket_id, index):
        """ get_back_forward_item(receiver, socket_id, index) -> Ask for the
        history item at index and return the result.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.get_back_forward_item(index)
    
    def get_history_item(self, receiver, socket_id, index):
        """ get_history_item(receiver, socket_id, index) -> Ask for the item
        at index 'index' and return the result.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.get_history_item(index)

    def get_current_item(self, receiver, socket_id):
        """ get_current_item(receiver, socket_id) -> Ask for the current
        item and return the result.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.get_current_item()

    def get_back_item(self, receiver, socket_id):
        """ get_back_item(receiver, socket_id) -> Ask for the previous item
        and return the result.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.get_back_item()

    def get_forward_item(self, receiver, socket_id):
        """ get_forward_item(receiver, socket_id) -> Ask for the next item
        and return the result.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.get_forward_item()

    def get_uri(self, receiver, socket_id):
        """ get_uri(receiver, socket_id) -> Ask for the current uri and
        return the result.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.get_uri()

    def get_history(self, receiver, socket_id, index):
        """ get_history(receiver, socket_id, index) -> Ask for the history
        overriding the current index with 'index' and return the result.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.get_history(index)

    def can_go_forward(self, receiver, socket_id):
        """ can_go_forward(receiver, socket_id) -> Ask if the browser
        can go forward and return whether it can or not.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.can_go_forward()

    def can_go_back(self, receiver, socket_id):
        """ can_go_back(receiver, socket_id) -> Ask whether the browser
        can go back and return if it can or not.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.can_go_back()

    def stop_loading(self, receiver, socket_id):
        """ stop_loading(receiver, socket_id) -> Tell the plug to stop
        loading the current page.

        """

        browser_plug = self.get_plug(socket_id)
        browser_plug.stop_loading()

    def reload(self, receiver, socket_id):
        """ reload(receiver, socket_id) -> Refresh the current page.

        """

        browser_plug = self.get_plug(socket_id)
        browser_plug.reload()

    def load_uri(self, receiver, uri, socket_id):
        """ load_uri(receiver, uri, socket_id) -> Load 'uri' in the browser
        plug.

        """

        browser_plug = self.get_plug(socket_id)
        return browser_plug.load_uri(uri)

    def go_back(self, receiver, socket_id):
        """ go_back(receiver, socket_id) -> Ask the plug to go back one step
        in history.

        """

        browser_plug = self.get_plug(socket_id)
        browser_plug.go_back()

    def go_forward(self, receiver, socket_id):
        """ go_forward(receiver, socket_id) -> Ask the plug to go one step
        forward in history.

        """

        browser_plug = self.get_plug(socket_id)
        browser_plug.go_forward()

    def zoom(self, receiver, socket_id, direction):
        """ Zoom the page in or out.

        """

        browser_plug = self.get_plug(socket_id)
        browser_plug.zoom(direction)

    def set_history(self, receiver, socket_id, history_str):
        """ set_history(reciever, socket_id, history_str) -> Tell the browser 
        to set its history to the history contained in 'history_str.'

        """

        browser_plug = self.get_plug(socket_id)
        browser_plug.set_history(history_str)

    def set_socket_id(self, receiver=None, socket_id=None):
        """ set_socket_id(receiver, socket_id) -> Create a new browser plug
        embedded in the socket owning 'socket_id.'

        """

        browser_plug = self.get_plug(socket_id)
        self._connect_plug(browser_plug)

    ##################
    # Plug callbacks #
    ##################
    def get_new_socket_id(self):
        """ get_new_socket_id -> Ask the main window for a socket id and 
        return it.

        """

        new_bus = dbus.SessionBus()
        obj = new_bus.get_object('com.browser.main%d' % os.getppid(), 
                self._main_path)
        socket_id = obj.get_socket_id(self._pid)
        return socket_id

    def plug_new_browser(self, browser_plug):
        """ plug_new_browser(browser_plug) -> Get a new socket id and 
        make a new browser plug using it.  Return the browser plug that
        was created.

        """

        socket_id = self.get_new_socket_id()
        self.set_socket_id(socket_id=socket_id)
        return self.get_plug(socket_id)

    def plug_new_tab(self, browser_plug, uri, flags):
        """ plug_new_tab(browser_plug, uri, flags) -> Ask for a new tab
        and depending on the value of 'flags' the tab will either be another
        process or part of this process.  Load 'uri' in the new tab.

        """

        self._sender.send_new_tab(uri, int(flags), 
                browser_plug.get_socket_id())

    def plug_title_changed(self, browser_plug, title):
        """ plug_title_changed(browser_plug, title) -> Send the new title
        to the parent tab when it changes.

        """

        self._sender.send_title(title, browser_plug.get_socket_id())

    def plug_back_forward(self, browser_plug, can_go_back, can_go_forward):
        """ plug_back_forward(browser_plug, can_go_back, can_go_forward) -> 
        Notify the parent tab if 'browser_plug' has back and/or forward
        history items.

        """

        self._sender.send_back_forward(can_go_back, can_go_forward, 
                browser_plug.get_socket_id())

    def plug_download_uri(self, browser_plug, filename, uri):
        """ plug_download_uri(browser_plug, filename, uri) -> Send the uri
        and suggested filename of a download to the parent tab.

        """

        self._sender.send_download_uri(filename, uri, 
                browser_plug.get_socket_id())

    def plug_embed_mime_uri(self, browser_plug, mimetype, uri, 
            handler_cmd_str):
        """ plug_embed_mime_uri(browser_plug, mimetype, uri, handler_cmd_str)
        -> Send the mimetype, uri, and the command to open the uri to the
        parent tab.

        """

        self._sender.send_embed_mime_uri(mimetype, uri, handler_cmd_str, 
                browser_plug.get_socket_id())

    def plug_uri_changed(self, browser_plug, uri):
        """ plug_uri_changed(browser_plug, uri) -> Send the new uri to the
        parent tab.

        """

        self._sender.send_uri(uri, browser_plug.get_socket_id())

    def plug_hover_uri(self, browser_plug, uri):
        """ plug_hover_uri(browser_plug, uri) -> Send the current uri that
        the mouse is hovering over in 'browser_plug' to its parent tab.

        """

        self._sender.send_hover_uri(uri, browser_plug.get_socket_id())

    def plug_favicon_uri(self, browser_plug, uri):
        """ plug_favicon_uri(browser_plug, uri) -> Send the favicon uri of
        the page loaded in 'browser_plug' to its parent tab.

        """

        self._sender.send_favicon_uri(uri, browser_plug.get_socket_id())

    def plug_progress_changed(self, browser_plug, progress):
        """ plug_progress_changed(browser_plug, progress) -> Send the current
        loading progress of 'browser_plug' to its parent tab.

        """

        self._sender.send_progress(progress, browser_plug.get_socket_id())

    def plug_show_hide_download(self, browser_plug):
        """ plug_show_hide_download(browser_plug) -> Tell the parent tab
        that the download manager's visibility should be toggled.

        """

        self._sender.send_show_hide_download(browser_plug.get_socket_id())

    def plug_message(self, browser_plug, message, color, data_color):
        """ plug_message(browser_plug, message, color, data_color) -> Send
        a log message to the main window.

        """

        self._sender.print_message(message, color, data_color)

if __name__ == '__main__':
    if argv[1:]:
        main_path = argv[1]
    else:
        main_path = ''
    # Setup the dbus main loop.
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    # Create and setup a new dbus bus for communication with the main window
    # and the parent tabs.
    bus = dbus.SessionBus()
    dbusname = dbus.service.BusName(PLUG_INTERFACE_NAME, bus)

    # Start the main signal handler of this tab process.
    plug = PlugMain(bus, main_path)
    plug.run()
