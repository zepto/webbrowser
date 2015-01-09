# This file is part of browser.  This is a plugin to catch move uris.
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

""" A tab plugin that watches requests and catches movie requests.

"""

import re
import os

import gtk
from glib import get_user_config_dir

class CatchMovie(object):
    """ CatchMovie -> Watch resource requests and catches movies based on
    a regex pattern.

    """

    def __init__(self, tab):
        """ Initialize the movie catcher.

        """

        self._log_func = tab.print_message
        self._send_download = tab._send_download
        self._movie_pat = None
        self._vid_ext_pat = None
        self._enabled = True

        self._path = '%s/webbrowser' % get_user_config_dir()

        self._tab = tab

    def run(self):
        """ run -> Finish initializing and run the movie catcher.

        """

        if not os.path.isfile('%s/movie.uri' % self._path):
            with open('%s/movie.uri' % self._path, 'w') as movie_file:
                movie_file.write('# Movie patterns\n\n')

        self._log_func("(Movie Catcher plugin): Running.", 32, '38;5;69')
        self.setup_movie_pat()

        # Connect the movie catcher to webview.
        self._tab.connect('resource-request', self._catch_movies) 
        self._tab.connect('populate-popup', self._popup) 

    def exit(self):
        """ exit -> Disconnect and stop the movie catcher.

        """

        try:
            self._tab.disconnect_by_func(self._catch_movies) 
            self._tab.disconnect_by_func(self._popup) 
        except:
            # Ignore errors.
            pass

    def setup_movie_pat(self):
        """ setup_movie_pat -> Build the regex pattern for searching for 
        movies from the file movie.uri in the current path.

        """

        pattern_list = []
        with open('%s/movie.uri' % self._path, 'r') as movie_file:
            for line in movie_file.readlines():
                if line[0] != '#' and line.strip():
                    pattern_list.append(line.strip())

        movie_str = r'|'.join(pattern_list)
        self._movie_pat = re.compile(r'(%s)' % movie_str, re.I)
        self._vid_ext_pat = re.compile(r'.*[\/=&]([^\/=&]*\.(fl.{1}|ogg|mp4|avi|mov|rm))([^a-zA-Z0-9]|$)', re.I)

    def _catch_movies(self, tab, uri):
        """ catch_movies -> Watches resource requests and catches movie requests.

        """

        if not self._enabled:
            return False

        match = self._movie_pat.search(uri)
        if match:
            self._log_func("movie: uri %s" % uri, 32, '38;5;69')
            if 'youtube.com' in uri:
                uri = uri.replace('&noflv=1', '').replace('noflv=1&', '')
                mp4_uri = uri.replace('&fmt=34', 
                        '&fmt=18').replace('fmt=34&', 'fmt=18&')
                self._log_func('youtube movie: mp4 uri http://www.youtube.com/watch?v=%s' % 
                        match.groups()[4], 32, 
                        '38;5;69')
                self._send_download(mp4_uri, 
                        '%s/%s.mp4' % (os.getenv('HOME'), match.groups()[4])) 
            elif 'megavideo' in uri:
                filename = '%s.flv' % match.groups()[6]
                self._send_download(uri, '%s/%s' % \
                        (os.getenv('HOME'), filename))
            elif 'googlevideo' in uri:
                filename = '%s.flv' % match.groups()[7]
                self._send_download(uri, '%s/%s' % \
                        (os.getenv('HOME'), filename))
            elif 'soundcloud' in uri:
                filename = '%s.mp3' % match.groups()[8]
                self._send_download(uri, '%s/%s' % \
                        (os.getenv('HOME'), filename))
            else:
                filename = match.groups()[-1]
                self._send_download(uri, '%s/%s' % \
                        (os.getenv('HOME'), filename))

    def _popup(self, tab, menu):
        """ _popup -> Builds and adds a menu item to enable/disable the 
        movie-catcher.

        """

        try:
            menu_item = gtk.CheckMenuItem('Catch Movies')
            menu_item.set_active(self._enabled)
            menu_item.connect('toggled', 
                    lambda *a: self.__setattr__('_enabled', not self._enabled))
            menu_item.show_all()
            self._tab._settings_menu.add(menu_item)
        except Exception as err:
            self._log_func("(Movie Catcher plugin): Error adding menu item: %s" % err, 32, '38;5;196')

Plugin = CatchMovie
