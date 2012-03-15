# This file is part of browser, and contains classes for embeding windows, 
# using the XEmbed protocol, in a gtk Socket.
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

import wnck

from classes import *

class EmbedSock(gtk.Socket):
    """ EmbedSock -> Socket object that starts an X app 
        and embeds it based on its xid """

    __gsignals__ = {
            'window-embeded' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_PYOBJECT,)),
            'window-name-changed' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
            'window-icon-changed' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
            'closing' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
            }

    def __init__(self):
        super(EmbedSock, self).__init__()

        self._screen = wnck.screen_get_default()
        self._screen.connect('window-opened', self._window_opened)
        self._screen.connect('application-opened', self._application_opened)

        self._window_connect_dict = {
                'name-changed' : self._window_name_changed,
                'icon-changed' : self._window_icon_changed,
                }

        self._app = None

    def run(self, app):
        """ run (app) ->
            Run app and embed it when it opens """

        self._app = subprocess.Popen(app)

    def close(self):
        self._app.send_signal(9)
        self._app.kill()
        self.emit('closing')
        return True

    def get_pid(self):
        if self._app:
            return self._app.pid

    def get_app(self):
        return self._app

    def _application_opened(self, screen, application):
        application_pid = application.get_pid()
        if self._app:
            if application_pid == self._app.pid:
                for signal, callback in self._window_connect_dict.iteritems():
                    application.connect(signal, callback)
                #self.add_id(application.get_xid())

    def _window_opened(self, screen, window):
        window_pid = window.get_pid()

        if self._app:
            if window_pid == self._app.pid:
                for signal, callback in self._window_connect_dict.iteritems():
                    window.connect(signal, callback)
                self.add_id(window.get_xid())
                self.emit('window-embeded', window)
                self.emit('window-icon-changed', window)
                self.emit('window-name-changed', window)

    def _window_icon_changed(self, window):
        self.emit('window-icon-changed', window)

    def _window_name_changed(self, window):
        self.emit('window-name-changed', window)

class EmbedApp(gtk.Socket):
    """ EmbedApp -> Socket object that starts an X app 
        and embeds it based on its xid """

    __gsignals__ = {
            'window-embeded' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_PYOBJECT,)),
            'window-name-changed' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
            'window-icon-changed' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
            'title-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING,)),
            'closing' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
            }

    def __init__(self):
        """ EmbedApp() -> A wrapper object to make it easier to embed an 
        external application window.  It also handles catching the title and 
        icon of the embeded window so the parent object can use them as it 
        wishes.

        """

        super(EmbedApp, self).__init__()

        # Get the default screen and connect some signals to catch when a
        # new window or application is opened.
        self._screen = wnck.screen_get_default()
        self._screen.connect('window-opened', self._window_opened)
        self._screen.connect('application-opened', self._application_opened)

        # Set the default title.
        self._title = 'Embedded Window'

        self._type = "EmbedApp"

        # Create an object to hold the window icon of the embedded window.
        self._icon = gtk.Image()
        self._icon.show_all()

        self._app = None

        # Setup a dictionary to link signals emitted by a window with their 
        # appropriate signal handlers.
        self._window_connect_dict = {
                'name-changed' : self._window_name_changed,
                'icon-changed' : self._window_icon_changed,
                }

    def run(self, app):
        """ run (app) ->
            Run app and embed it when it opens.
            
        """

        self._app = subprocess.Popen(app)

    def close(self):
        """ close() -> Close the embedded app and emit a 'closing' signal so
        its parent can do any cleanup necessary.

        """

        if self._app:
            self._app.send_signal(9)
            self._app.kill()

        self.emit('closing')

        return True

    def get_title(self):
        """ get_title() -> Returns the saved title of the embedded window.

        """

        return self._title

    def get_icon(self):
        """ get_icon() -> Returns the saved icon of the embedded window.

        """

        return self._icon

    def get_pid(self):
        """ get_pid() -> Returns the pid of the embedded app.

        """

        if self._app:
            return self._app.pid

    def get_app(self):
        """ get_app() -> Returns the embedded app process.

        """

        return self._app

    def set_icon(self, icon_name):
        """ set_icon(icon_name) -> Set the icon from icon_name.

        """

        self._icon.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)

    def _application_opened(self, screen, application):
        """ _application_opened(screen, application) -> If application is the
        app started earlier then this method will connect some signals for
        application to signal-handlers.

        """

        application_pid = application.get_pid()
        if self._app:
            if application_pid == self._app.pid:
                for signal, callback in self._window_connect_dict.iteritems():
                    application.connect(signal, callback)

                self._screen.disconnect_by_func(self._application_opened)


    def _window_opened(self, screen, window):
        """ _window_opened(screen, window) -> If window is the app started 
        earlier then this method will connect some signals for window to 
        signal-handlers.

        """

        window_pid = window.get_pid()

        if self._app:
            if window_pid == self._app.pid:
                for signal, callback in self._window_connect_dict.iteritems():
                    window.connect(signal, callback)

                self._screen.disconnect_by_func(self._window_opened)

                self.add_id(window.get_xid())
                self._window_icon_changed(window)
                self._window_name_changed(window)

                self.emit('window-embeded', window)
                self.emit('title-changed', window.get_name())

    def _window_icon_changed(self, window):
        pixbuf_icon = window.get_icon()
        if pixbuf_icon:
            pixbuf_icon = pixbuf_icon.scale_simple(16, 16, 
                    gtk.gdk.INTERP_BILINEAR)
            self._icon.set_from_pixbuf(pixbuf_icon)
        self.emit('window-icon-changed', window)

    def _window_name_changed(self, window):
        self._title = window.get_name()
        self.emit('window-name-changed', window)

    @property
    def type(self):
        return self._type
