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

""" A tab plugin that runs user java scripts when the page is loaded.

"""

import os
import glob

import gtk
from glib import get_user_config_dir

from defaults import APP_NAME

class UserScripts(object):
    """ UserScripts -> Load and run javascripts when the page is loaded.

    """

    def __init__(self, tab):
        """ Initialize the script runner.

        """

        self._path = '%s/%s/scripts' % (get_user_config_dir(), APP_NAME)
        self._profile_path = '%s/%s/%s/scripts' % \
                (get_user_config_dir(), APP_NAME, profile)

        self._tab = tab
        self._log_func = tab.print_message
        self._enabled = True

    def run(self):
        """ Do the final initialization and run.

        """

        self._log_func("(User Script plugin): Running.", 32, '38;5;196')

        # Connect to the browser.
        self._tab.connect('load-status', self._page_load_changed)
        self._tab.connect('populate-popup', self._popup)

    def exit(self):
        """ exit -> Disconnect and stop.

        """

        try:
            self._tab.disconnect_by_func(self._page_load_changed)
            self._tab.disconnect_by_func(self._popup)
        except:
            # Ignore errors.
            pass

    def _page_load_changed(self, tab, load_status):
        """ _page_load_changed -> Call the script runner when the page is 
        loaded.

        """

        if load_status == 2:
            self._run_user_scripts()
            
    def _run_user_scripts(self):
        """ _run_user_scripts -> Run user provided javascript.

        """

        # Return if script running is disabled.
        if not self._enabled:
            return

        for path in [self._path, self._profile_path]:
            # If there are no user scripts return.
            if not os.path.isdir(path):
                continue

            browser = self._tab.get_browser()

            # Loop through all the javascripts in the path and run them.
            for filename in glob.iglob('%s/*.js' % path):
                # Don't bother with anything but files.
                if not os.path.isfile(filename):
                    continue

                self._log_func("(User Script plugin): Running User Script %s." % filename, 32, '38;5;196')
                with open(filename, 'r') as script_file:
                    browser.execute_script(script_file.read())

    def _popup(self, tab, menu):
        """ _popup -> Builds and adds a menu item to enable/disable the 
        script runner.

        """

        try:
            menu_item = gtk.CheckMenuItem('Enable _User Scripts')
            menu_item.set_active(self._enabled)
            menu_item.connect('toggled', 
                lambda *a: self.__setattr__('_enabled', not self._enabled))
            menu_item.show_all()
            self._tab._settings_menu.add(menu_item)
        except Exception as err:
            self._log_func("(User Script plugin):  Error adding menu item: %s" % err, 32, '38;5;196')

Plugin = UserScripts
