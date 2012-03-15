# This file is part of browser, and contains the default variables.
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

""" Default global variables.

"""

import os

# Application name.
APP_NAME = 'webbrowser'

# Set the global main interface name.
MAIN_INTERFACE_NAME = "com.browser.main%d" % os.getpid()

# Define the interface used when connecting to a tab over dbus.
PLUG_INTERFACE_NAME = "com.browser.plug%d" % os.getpid()

