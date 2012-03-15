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

""" Main plugin template.

"""

import os

from plugin_loader import PluginBase

class Example(PluginBase):
    """ Plugin class

    """

    def __init__(self, browser):
        """ Plugin

        """

        super(Example, self).__init__(browser)

    def run(self):
        """ Initialize plugin.

        """

        try:
            pass
        except:
            pass

    def exit(self):
        """ Unload plugin.

        """

        try:
            pass
        except:
            pass

Plugin = Example
