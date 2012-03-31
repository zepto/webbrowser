# This file is part of browser.  This is an agen switcher plugin.
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

""" A tab plugin that allows the user to switch the browser agent.

"""

import gtk

class AgentSwitcher(object):
    """ AdBlock -> Load ad patterns from a file and block requests to uris
    that match any of those patterns.

    """

    def __init__(self, tab):
        """ Initialize the ad blocker.

        """

        self._tab = tab

        # Define the user agents.
        self._agent_dict = {
                'Default': self._tab.get_browser_setting('user-agent'), #'Mozilla/5.0 (X11; U; Linux i686; en-us) AppleWebKit/531.2+ (KHTML, like Gecko) Safari/531.2+',
                'Google Chrome':'Mozilla/5.0 (X11; Linux i686) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.142 Safari/535.19',
                'Firefox 11.0': 'Mozilla/5.0 (X11; Linux i686; rv:11.0) Gecko/20100101 Firefox/11.0',
                'Opera 12.00': 'Opera/9.80 (Windows NT 6.1; U; es-ES) Presto/2.9.181 Version/12.00',
                'Konqueror': 'Mozilla/5.0 (compatible; Konqueror/4.5; FreeBSD) KHTML/4.5.4 (like Gecko)'
                }
        self._agent = 'Default'

    def run(self):
        """ Do the final initialization and run the agent switcher.

        """

        # Connect the agent switcher to browser.
        self._tab.connect('populate-popup', self._popup) 

    def exit(self):
        """ exit -> Disconnect and stop the agent switcher.

        """

        try:
            self._tab.disconnect_by_func(self._popup)
            self._tab.set_browser_setting('user-agent', 
                    self._agent_dict['Default'])
        except:
            # Ignore errors.
            pass

    def _agent_switch(self, menuitem, name):
        """ _agent_switch -> Switch the user agent to name.

        """

        self._agent = name
        self._tab.set_browser_setting('user-agent', self._agent_dict[name])

    def _popup(self, tab, menu):
        """ _popup -> Builds and adds a menu to switch browser agents to the 
        popup menu.

        """

        agent_menu = gtk.Menu()
        current_agent_str = self._tab.get_browser_setting('user-agent')
        for name, agent_str in self._agent_dict.iteritems():
            menuitem = gtk.CheckMenuItem(name)
            if agent_str == current_agent_str:
                menuitem.set_active(True)
                self._agent = name
            menuitem.connect('toggled', self._agent_switch, name)
            agent_menu.add(menuitem)

        icon = gtk.Image()
        icon.set_from_icon_name('gtk-info', gtk.ICON_SIZE_MENU)
        menu_item = gtk.ImageMenuItem()
        agent_item = gtk.ImageMenuItem()
        agent_item.set_image(icon)
        agent_item.set_label('Agent Switcher')
        agent_item.set_submenu(agent_menu)
        agent_item.show_all()
        menu.add(agent_item)

Plugin = AgentSwitcher
