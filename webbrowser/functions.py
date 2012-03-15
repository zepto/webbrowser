# This file is part of browser, and contains miscellaneous functions.
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

import warnings
import subprocess
from time import strftime
from contextlib import contextmanager

import gtk
import glib

debug = True
def print_message(message, color=None, data_color=None):
    if debug:
        date = strftime('%h %e %H:%M:%S')
        if color:
            if not data_color:
                message_list = message.split(':', 1)
                messagestr = "[38;5;75m%s [0;%sm%s[m:%s" % (date, color, message_list[0], ''.join(message_list[1:]))
            else:
                message_list = message.split(':', 2)
                messagestr = "[38;5;75m%s [0;%sm%s[m:[%sm%s[m:%s" % (date, color, message_list[0], data_color, message_list[1], ''.join(message_list[2:]))
        else:
            messagestr = "[38;5;75m%s[m" % (date, message)
        print(messagestr)

@contextmanager
def redirect_warnings(warning_func):
    """ _redirect_warnings(warning_func) -> Setup warning redirector to 
    redirect warnings to warning_func.  Use this function with 'with' 
    statements. 
    
    """

    # Save old warning function
    old_showwarning = warnings.showwarning

    # Override default warning function
    warnings.showwarning = warning_func

    try:
        # Run commands in 'with' statement
        yield
    finally:
        # After 'with' block exits restore showwarning function
        warnings.showwarning = old_showwarning

def extern_load_uri(uri):
    """ extern_load_uri(uri) -> First attempts to load the uri with 
    gtk.show_uri.  If that fails it trys xdg-open, gnome-open, and exo-open.

    """

    try:
        # Try gtk.show_uri.
        ret = gtk.show_uri(gtk.gdk.screen_get_default(), uri, 
                int(glib.get_current_time()))
        if ret:
            return True
    except Exception as err:
        print("Error (%s) while loading uri: %s" % (err, uri))

    app_list = ['xdg-open', 'gnome-open', 'exo-open']

    for app in app_list:
        try:
            proc_tup = glib.spawn_async([app, uri], 
                    flags=glib.SPAWN_SEARCH_PATH)
        except Exception as err:
            print("Error (%s) while loading uri (%s) with app (%s)" % \
                    (err, uri, app))

            # Go to the next app if there was an error.
            continue

        # If it gets here than it spawned without error.
        return True

    return False


