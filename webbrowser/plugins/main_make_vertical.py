# This file is part of browser.  This is a plugin to make the bottom panel a 
# virtical panel.
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

""" Make the bottom panel a vertical side panel.

"""

import gtk

# Make it not auto-load when the plugin manager starts.
AUTO_LOAD = False

class MakeVertical(object):
    """ MakeVerticl -> Make the bottom panel a vertical side panel.

    """

    def __init__(self, browser):
        """ Initialize the switcher.

        """

        self._browser = browser
        self._pos = 0

    def run(self):
        """ Make the panel vertical.

        """

        vpaned = self._browser._window.get_children()[0].get_children()[0]
        
        # Save the current position so we can restore it later.
        self._pos = vpaned.get_position()

        vpaned.set_orientation(gtk.ORIENTATION_HORIZONTAL)

        # Set the position to half the total width, because 
        # allocation = (x, y, width, height).
        vpaned.set_position(vpaned.allocation[2] / 2)

    def exit(self):
        """ exit -> Reset the panel to a horizontal bottom panel.

        """

        vpaned = self._browser._window.get_children()[0].get_children()[0]
        vpaned.set_orientation(gtk.ORIENTATION_VERTICAL)
        vpaned.set_position(self._pos)

Plugin = MakeVertical
