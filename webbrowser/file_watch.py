# This file is part of browser, and contains file watching classes.
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

""" A couple different file watching objects.

"""

import os
import fcntl
import signal
import threading
from time import sleep

import glib

try:
    from pyinotify import WatchManager, Notifier, ThreadedNotifier, EventsCodes, ProcessEvent
    pyinotify = True
except ImportError as err:
    print("Disabling pyinotify.")
    ProcessEvent = object
    pyinotify = False

# Create a class to process events.
class ProcessFileEvents(ProcessEvent):
    """ A subclass of pyinotify.ProcessEvent. """

    def __init__(self):
        """ Process inotify events, and check to see if any of the correct
        files were modified.

        """

        super(ProcessFileEvents, self).__init__()

        self._file_callback_dict = {}

    def has_file(self, filename):
        """ Returns a boolean indecating if the file is being watched.

        """

        return filename in self._file_callback_dict

    def add_file(self, filename, callback, *user_data):
        """ add_file(filename, callback, *user_data) -> Add a file to watch
        with its callback and optional user_data.

        """

        self._file_callback_dict[filename] = (callback, user_data)

    def remove_file(self, filename):
        """ remove_file(filename) -> Remove the file from the watch list.

        """

        return self._file_callback_dict.pop(filename, None)

    def process_IN_MODIFY(self, event):
        """ Process modify events.

        """

        filename = os.path.join(event.path, event.name)
        callback_data = self._file_callback_dict.get(filename, ())

        if callback_data:
            callback = callback_data[0]
            callback(callback_data[1:])

class FileWatcher(ProcessEvent):

    """ FileWatcher -> Starts an INotify thread to watch a directory for
    file changes.

    """

    def __init__(self):
        """ FileWatcher(directory) -> Watch the directory for changes.

        """

        if not pyinotify:
            raise Exception("pyinotify is not loaded.")

        super(FileWatcher, self).__init__()

        self._file_callback_dict = {}

        self._watch_manager = WatchManager()
        self._events_mask = EventsCodes.ALL_FLAGS['IN_MODIFY']

        self._notifier = ThreadedNotifier(self._watch_manager, self)
        self._notifier.setDaemon(True)

    @classmethod
    def check(cls):
        """ Returns true if pyinotify is loaded otherwise false.

        """

        return pyinotify

    def is_running(self):
        """ Returns a boolean indecating the state of the notifier.

        """

        return self._notifier.isAlive()

    def start(self):
        """ Start the notifier thread.

        """

        self._notifier.start()

    def stop(self):
        """ Stop the notifier thread.

        """

        self._notifier.stop()

    def add_directory(self, directory):
        """ add_directory(directory) -> Add a directory to watch.

        """

        dir_watch = self._watch_manager.add_watch(directory, self._events_mask, rec=True)

    def remove_directory(self, directory):
        """ remove_directory(directory) -> Remove a directory from the watch.

        """

        self._watch_manager.rm_watch(directory, rec=True)

    def has_file(self, filename):
        """ Returns a boolean indecating if the file is being watched.

        """

        return filename in self._file_callback_dict

    def add_file(self, filename, callback, *user_data):
        """ add_file(filename, callback, *user_data) -> Add a file to watch
        with its callback and optional user_data.

        """

        self._file_callback_dict[filename] = (callback, user_data)

    def remove_file(self, filename):
        """ remove_file(filename) -> Remove the file from the watch list.

        """

        return self._file_callback_dict.pop(filename, None)

    def process_IN_MODIFY(self, event):
        """ Process modify events.

        """

        filename = os.path.join(event.path, event.name)
        callback_data = self._file_callback_dict.get(filename, ())

        if callback_data:
            callback = callback_data[0]
            glib.idle_add(callback, callback_data[1:])

#class FileWatch(threading.Thread):
class FileWatch(object):

    """ FileWatch -> Watches for changes in a files mtime and calls a user
    supplied function.

    """

    def __init__(self, filename, callback, *user_data):
        """ FileWatch(filename, callback, *user_data) -> Watches the file, and 
        calls the callback function with the userdata when the mtime changes.

        """

        super(FileWatch, self).__init__()

        self._filename = filename
        self._callback = callback
        self._user_data = user_data

        self._mtime = os.path.getmtime(filename)
        self._watch = True
        self._fd = None
        self._directory = os.path.dirname(self._filename)

    def watch(self):
        """ watch -> Check if the file changed, and run the callback if it
        did.

        """

        try:
            mtime = os.path.getmtime(self._filename)
        except:
            return self._watch

        if self._mtime != mtime:
            self._mtime = mtime
            self._callback(self, self._user_data)

        return self._watch

    def _changed(self, signum, frame):
        """ _changed(signum, frame) -> Called when the directory changes.
        Checks watched file to see if it is what changed.

        """

        try:
            mtime = os.path.getmtime(self._filename)
        except:
            return False

        if self._mtime != mtime:
            self._mtime = mtime
            self._callback(self, *self._user_data)

    def run(self):
        """ run -> Start the file watching thread.

        """

        self._watch = True
        while self._watch:
            mtime = os.path.getmtime(self._filename)
            if self._mtime != mtime:
                self._mtime = mtime
                self._callback(self, self._user_data)
            sleep(1)

    def start_watcher(self):
        """ start -> Open the file and start the notifier.

        """

        signal.signal(signal.SIGIO, self._changed)
        self._fd = os.open(self._directory, os.O_RDONLY)
        fcntl.fcntl(self._fd, fcntl.F_SETSIG, 0)
        fcntl.fcntl(self._fd, fcntl.F_NOTIFY, 
                fcntl.DN_MODIFY | fcntl.DN_CREATE | fcntl.DN_MULTISHOT)

    def stop(self):
        """ stop -> Stop watching the file.

        """

        self._watch = False
        if self._fd:
            os.close(self._fd)
            self._fd = None

