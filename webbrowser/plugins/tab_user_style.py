# This file is part of browser.  This is a plugin to run user scripts.
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

""" A tab plugin that loads a user stylesheet.

"""

import os
import glob

import gtk
from glib import get_user_config_dir

from defaults import APP_NAME

class UserStyle(object):
    """ UserStyle -> Sets a user stylesheet.

    """

    def __init__(self, tab):
        """ Initialize the styles loader.

        """

        self._path = '%s/%s/styles' % (get_user_config_dir(), APP_NAME)
        self._profile_path = '%s/%s/%s/styles' % \
                (get_user_config_dir(), APP_NAME, profile)

        self._tab = tab
        self._log_func = tab.print_message
        self._enabled = True

    def run(self):
        """ Do the final initialization and run.

        """

        self._log_func("(User Stylesheet plugin): Running.", 32, '38;5;196')
        self._load_stylesheet()

        # Connect to the browser.
        self._tab.connect('populate-popup', self._popup)

    def exit(self):
        """ exit -> Disconnect and stop.

        """

        try:
            self._tab.set_browser_setting('user-stylesheet-uri', None, False)
            self._tab.disconnect_by_func(self._popup)
        except:
            # Ignore errors.
            pass

    def _load_stylesheet(self):
        """ _load_stylesheet -> Load user stylesheet.

        """

        # Return if plugin is disabled.
        if not self._enabled:
            return

        for path in [self._path, self._profile_path]:
            # If there are no stylesheets return.
            if not os.path.isdir(path):
                continue

            # Loop through all the stylesheets in the path and run them.
            for filename in glob.iglob('%s/*.css' % path):
                # Don't bother with anything but files.
                if not os.path.isfile(filename):
                    continue

                self._log_func("(User Stylesheet plugin): Loading Stylesheet %s." % filename, 32, '38;5;196')
                self._tab.set_browser_setting('user-stylesheet-uri', 'file://%s' % filename, False)

    def _toggle(self, menuitem):
        """ _toggle -> Enable/disable style loader.

        """

        self._enabled = not self._enabled
        if not self._enabled:
            self._tab.set_browser_setting('user-stylesheet-uri', None, False)
        else:
            self._load_stylesheet()


    def _popup(self, tab, menu):
        """ _popup -> Builds and adds a menu item to enable/disable the 
        stylesheet loader.

        """

        try:
            menu_item = gtk.CheckMenuItem('Enable _User Stylesheets')
            menu_item.set_active(self._enabled)
            menu_item.connect('toggled', self._toggle) 
            menu_item.show_all()
            self._tab._settings_menu.add(menu_item)
        except Exception as err:
            self._log_func("(User Stylesheets plugin):  Error adding menu item: %s" % err, 32, '38;5;196')

Plugin = UserStyle
