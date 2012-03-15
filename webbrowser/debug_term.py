# This file is part of browser, and contains the DebugTerm class used to 
# send messages to Debugdbus over dbus.
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

import dbus
import dbus.service
import dbus.mainloop.glib
import dbus.gobject_service

class DebugTerm(dbus.service.Object):
    """ DebugTerm (bus) -> An object to communicate with the debug terminal
    through dbus on bus 'bus' 
    
    """

    DEBUG_INTERFACE = "com.browser.debug%d" % os.getpid()

    def __init__(self, bus):
        """ DebugTerm(bus) -> An Object to communicate with the Debugdbus 
        object over dbus 'bus.' 
        
        """

        super(DebugTerm, self).__init__(bus, '/debug_term')

    @dbus.service.signal(dbus_interface=DEBUG_INTERFACE,signature='u')
    def change_pid(self, pid):
        """ change_pid(pid) -> Set the debug terminal to listen for
        connections from pid 'pid.' 
        
        """

        pass

    @dbus.service.signal(dbus_interface=DEBUG_INTERFACE,signature='sus')
    def print_message_signal(self, message, color=0, data_color=''): 
        """ print_message_signal(message, color=0, data_color='') ->
        Sends the print_message command to the debug terminal with the message.
        Optionally it is colored using ansi color 'color' and 'data_color.' 
        
        """

        pass

    @dbus.service.signal(dbus_interface=DEBUG_INTERFACE)
    def exit(self):
        """ exit() -> Send exit command to the debug terminal. 
        
        """

        pass
