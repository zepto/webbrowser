# This is a template plugin.
#
# Copyright (C) 2010  Josiah Gordon <josiahg@gmail.com>
#
# This is free software: you can redistribute it and/or modify
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

""" A tab plugin template.

"""

import os
import glob

class Template(object):
    """ Template -> template.

    """

    def __init__(self, tab):
        """ Initialize the script runner.

        """

        self._tab = tab

    def run(self):
        """ Do the final initialization and run.

        """

        pass

    def exit(self):
        """ exit -> Disconnect and stop.

        """

        try:
            pass
        except:
            # Ignore errors.
            pass

Plugin = Template
