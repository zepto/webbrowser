# This file is part of browser, and contains the Debugdbus for printing 
# debug messages received over dbus.
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

import gtk
import dbus
import dbus.service
import dbus.mainloop.glib
import os
from time import strftime

class Debugdbus(object):
    
    INTERFACE = "com.browser.debug%d"

    def __init__(self):
        self._debug = True
        self._setup_bus()

    def _setup_bus(self, pid=os.getppid()):
        bus_receiver_dict = {
                'print_message_signal': self._print_message,
                'change_pid': self._change_pid,
                'exit': self._exit,
                }

        bus = dbus.SessionBus()
        for signal_name, handler_func in bus_receiver_dict.iteritems():
            bus.add_signal_receiver(handler_func, dbus_interface=Debugdbus.INTERFACE % pid, signal_name=signal_name)

    def run(self):
        gtk.main()

    def _exit(self):
        gtk.main_quit()

    def _toggle_debug(self, value):
        self._debug = value

    def _change_pid(self, pid):
        self._setup_bus(pid)

    def _print_message(self, message, color, data_color):
        if not message.strip():
            return False
        if self._debug:
            date = strftime('%h %e %H:%M:%S')
            if color != 0:
                if data_color == '':
                    message_list = message.split(':', 1)
                    messagestr = "[38;5;75m%s [0;%sm%s[m:%s" % (date, color, message_list[0], ''.join(message_list[1:]))
                else:
                    message_list = message.split(':', 2)
                    if len(message_list) > 2:
                        messagestr = "[38;5;75m%s [0;%sm%s[m:[%sm%s[m:%s" % (date, color, message_list[0], data_color, message_list[1], ''.join(message_list[2:]))
                    else:
                        message_list = message.split(':', 1)
                        messagestr = "[38;5;75m%s [0;%sm%s[m:%s" % (date, color, message_list[0], ''.join(message_list[1:]))
            else:
                messagestr = "[38;5;75m%s[m %s" % (date, message)
            print(messagestr)

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    debug_output = Debugdbus()
    debug_output.run()
