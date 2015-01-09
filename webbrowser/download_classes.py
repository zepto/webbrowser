# This file is part of browser, and contains the download classes.
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

""" Provides classes to download using urllib and aria2c.  Also a gui download
manager tab for the browser.

"""

import os
import random
import xmlrpclib
import threading
import thread
import time
from time import strftime
from select import select, poll, POLLIN
from fcntl import fcntl, F_SETFL, F_GETFL
import urllib
import subprocess
import string
import re

import gtk
import gobject
import glib

from classes import SaveDialog, OpenDialog

class DownloadManager(gtk.ScrolledWindow):

    def __init__(self):
        super(DownloadManager, self).__init__()

        self._title = "Downloads"
        self._icon = gtk.Image()
        self.set_icon('emblem-downloads')
        self._current_folder = os.getenv('HOME')
        self._thread_dict = {}

        # A regex pattern for determining if a download is a movie.
        #self._movie_pat = re.compile(r'[\/=&]([^\/=&]*\.(fl.{1}|ogg|mp4|avi|mov|rm))([^a-zA-Z0-9]|$)', re.I)
        self._movie_pat = re.compile(r'[\/=&]?([^\/=&]*\.(ifl|fl.{1}|iflv|ogg|webm|mkv|m4v|mp4|avi|mov|rm|mp3|wav))([^a-zA-Z0-9]|$)', re.I)

        self.set_policy('automatic', 'automatic')
        self.set_shadow_type(gtk.SHADOW_IN)

        column_tup = (
                ('Progress', gtk.CellRendererProgress(), {'value':0}, False, 
                    gtk.ProgressBarStyle),
                ('Total Size', gtk.CellRendererText(), {'text':1}, True, str),
                ('Completed Size', gtk.CellRendererText(), {'text':2}, True, 
                    str),
                ('Filename', gtk.CellRendererText(), {'text':3}, True, str),
                ('URI', gtk.CellRendererText(), {'text':4}, True, str),
                )

        self._download_view = gtk.TreeView()
        self._download_view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self._download_view.set_rubber_banding(True)

        col_types = []
        for (title, renderer, value, resizable, col_type) in column_tup:
            column = gtk.TreeViewColumn(title, renderer, **value)
            column.set_resizable(resizable)
            self._download_view.append_column(column)
            col_types.append(col_type)

        self._download_store = gtk.ListStore(*col_types)
        self._download_view.set_model(self._download_store)

        self._download_view.connect('key-press-event', self._view_key_pressed)
        self._download_view.connect('button-release-event', 
                self._view_button_released)

        self._menu = self._build_menu()

        self._aria_server = Aria2cServer()
        #self._aria_server.start()

        # Keep track of the clipboard.
        self._clipboard = gtk.clipboard_get('PRIMARY')
        self._clipboard.connect('owner-change', self._clipboard_owner_change)

        self.add(self._download_view)
        self.show_all()

    def _build_menu(self):
        menu = gtk.Menu()

        item_tup = (
                ('_export_list_item', ('gtk-save', '_Export List', False, 
                    None, self._export_list_button_released)),
                gtk.SeparatorMenuItem(),
                ('_add_uri_item', ('gtk-add', '_Add Uri', True, None, 
                    self._add_uri_button_released)),
                gtk.SeparatorMenuItem(),
                ('_start_item', ('gtk-media-play-ltr', '_Start', False, 
                    None, self._start_button_released)),
                ('_pause_item', ('gtk-media-pause', '_Pause', False, None, 
                    self._pause_button_released)),
                gtk.SeparatorMenuItem(),
                ('_rename_item', ('gtk-edit', '_Rename', False, None, 
                    self._rename_button_released)),
                ('_copy_uri_item', ('edit-copy', '_Copy Uri', False, None, 
                    self._copy_uri_button_released)),
                gtk.SeparatorMenuItem(),
                ('_clear_item', ('gtk-clear', 'C_lear List', False, None, 
                    self._clear_button_released)),
                ('_clear_completed_item', ('gtk-clear', 
                    'Clear Completed Downloads', True, None,
                    self._clear_completed_button_released)),
                ('_remove_download_item', ('list-remove', 'Remove _Selected', 
                    False, 'Delete', self._remove_download_button_released)),
                gtk.SeparatorMenuItem(),
                ('_restart_server_item', ('gtk-refresh', 
                    'Rest_art Aria2c Server', True, None, 
                    self._restart_server_button_released)),
                )

        accel_group = gtk.AccelGroup()
        menu.set_accel_group(accel_group)

        for menu_item in item_tup:
            if type(menu_item) == tuple:
                item_name, (icon_name, label_text, is_sensitive, accel, 
                        clicked_callback) = menu_item
                icon = gtk.Image()
                icon.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)
                item = gtk.ImageMenuItem()
                item.set_image(icon)
                item.set_label(label_text)
                item.set_use_underline(True)
                item.set_sensitive(is_sensitive)
                item.connect('button-release-event', clicked_callback)
                self.__setattr__(item_name, item)
                if accel:
                    keyval, modifier = gtk.accelerator_parse(accel)
                    item.add_accelerator('activate', accel_group, keyval, 
                            modifier, gtk.ACCEL_VISIBLE)
            else:
                item = menu_item
            menu.add(item)
            
        menu.show_all()

        return menu

    def _view_button_released(self, download_view, event):
        """ _view_button_released() Called when the mouse button is released 
        after clicking on the download list. 
        
        """

        # Get the item that is under the mouse
        path = download_view.get_path_at_pos(int(event.x), int(event.y))
        selection = download_view.get_selection()
        if path:
            # Select the item under the mouse if one or fewer items are 
            # selected.
            if selection.count_selected_rows() <= 1 and event.button == 3 \
                    or event.button == 2:
                selection.unselect_all()
                selection.select_path(path[0])

            # Enable the copy_uri item when the mouse is over a download
            row = path[0]
            iter = self._download_store.get_iter(row)
            self._update_selected(iter)
            self._copy_uri_item.set_sensitive(True)
            self._remove_download_item.set_sensitive(True)
        else:
            # Disable the pause, start, rename, and copy_uri items when the 
            # mouse is not over a download in the list
            self._pause_item.set_sensitive(False)
            self._start_item.set_sensitive(False)
            self._rename_item.set_sensitive(False)
            self._copy_uri_item.set_sensitive(False)
            self._remove_download_item.set_sensitive(False)

            selection.unselect_all()
            
        if event.button == 3:
            # Enable/Disable the clear_item and export_list_item based on 
            # whether the download list is empty or not
            self._clear_item.set_sensitive(len(self._download_store) > 0)
            self._export_list_item.set_sensitive(len(self._download_store) > 0)

            # Pop up menu
            self._menu.popup(None, None, None, event.button, event.time, None)

            return True
        elif event.button == 2:
            # Remove the downloads under the mouse from the list when the 
            # middle mouse button is clicked
            self._remove_selected()

            return True

        return False

    def _view_key_pressed(self, download_view, event):
        """ _view_key_pressed -> Called when a key is pressed on the download
        list.
        
        """

        if event.keyval == gtk.gdk.keyval_from_name('Delete'):
            self._remove_selected()
            return True

        return False

    def _update_selected(self, iter):
        uri = self._get_uri(iter)

        download_thread = self._thread_dict.get(uri, None)

        if download_thread:
            self._pause_item.set_sensitive(download_thread.is_alive())
            self._start_item.set_sensitive(not download_thread.is_alive())
            self._rename_item.set_sensitive(not download_thread.is_alive())
        else:
            self._pause_item.set_sensitive(False)
            self._start_item.set_sensitive(True)
            self._rename_item.set_sensitive(True)

    def _remove_download_button_released(self, remove_item, event):
        remove_item.parent.popdown()
        
        self._remove_selected()

    def _restart_server_button_released(self, restart_server_item, event):
        if self._aria_server.is_running():
            pid = self._aria_server.get_pid()
            self._aria_server.stop()
            if pid:
                try:
                    os.kill(pid, 9)
                except:
                    pass
        self._aria_server.start()

    def _start_button_released(self, start_item, event):
        selection = self._download_view.get_selection()

        for row in selection.get_selected_rows()[1]:
            iter = self._download_store.get_iter(row)

            self._start_download(iter)

    def _pause_button_released(self, pause_item, event):
        selection = self._download_view.get_selection()

        for row in selection.get_selected_rows()[1]:
            iter = self._download_store.get_iter(row)
            uri = self._get_uri(iter)
            download_thread = self._thread_dict.get(uri, None)
            if download_thread:
                download_thread.stop()

    def _export_list_button_released(self, export_list_item, event):
        save_dialog = SaveDialog('downloads_list', self._current_folder)
        out_filename = save_dialog.run()
        self._current_folder = save_dialog.get_folder()
        if out_filename:
            uri_list = []
            for row in self._download_store:
                iter = row.iter
                filename = self._get_filename(iter)
                uri = self._get_uri(iter)
                uri_list.append("""wget '%s' -O '%s'\n""" % (uri, filename))
            out_file = open(out_filename, 'w')
            out_file.write(''.join(uri_list))
            out_file.close()

    def _add_uri_button_released(self, add_uri_item, event):
        clipboard = gtk.clipboard_get('CLIPBOARD')
        uri = clipboard.wait_for_text()
        if not uri:
            clipboard = gtk.clipboard_get('PRIMARY')
            uri = clipboard.wait_for_text()
        if uri:
            filename = uri.split('/')[-1]
            self.add_download(uri, filename)

    def _clear_button_released(self, clear_item, event):
        """ _clear_button_released -> Remove all but the active downloads
        from the list.

        """

        for row in self._download_store:
            iter = row.iter
            self._remove_item(iter, clear_running=False)

    def _clear_completed_button_released(self, clear_completed_item, event):
        """ _clear_completed_button_released -> Remove the completed downloads
        from the list.

        """

        for row in self._download_store:
            iter = row.iter
            if self._download_store.get_value(iter, 0) == 100:
                self._remove_item(iter)

    def _rename_button_released(self, rename_item, event):
        selection = self._download_view.get_selection()

        for row in selection.get_selected_rows()[1]:
            iter = self._download_store.get_iter(row)
            filename = self._get_filename(iter)
            save_dialog = SaveDialog(filename, self._current_folder)
            new_filename = save_dialog.run()
            self._current_folder = save_dialog.get_folder()
            if new_filename:
                self._set_filename(iter, new_filename)

    def _copy_uri_button_released(self, copy_item, event):
        selection = self._download_view.get_selection()
        uri_list = []
        for row in selection.get_selected_rows()[1]:
            iter = self._download_store.get_iter(row)
            uri_list.append(self._get_uri(iter))

        clipboard = gtk.clipboard_get('CLIPBOARD')
        clipboard.set_text('\n'.join(uri_list))
        clipboard.store()

    def _start_download(self, iter):
        filename = self._get_filename(iter)
        uri = self._get_uri(iter)
        progress_bar = BarProgress(self._set_progress, iter) 
        #if self._aria_server.is_running():
            #try:
                #download_thread = Aria2cClient(uri, filename, progress_bar, 
                        #self._aria_server.get_uri())
            #except:
                #download_thread = Aria2cDownload(uri, filename, progress_bar)
        #else:
            #download_thread = Download(uri, filename, progress_bar)
        try:
            download_thread = Aria2cDownload(uri, filename, progress_bar)
        except:
            download_thread = Download(uri, filename, progress_bar)
        download_thread.start()
        self._thread_dict[uri] = download_thread

    def _remove_item(self, iter, clear_running=True):
        uri = self._get_uri(iter)
        download_thread = self._thread_dict.get(uri, None)
        if download_thread:
            if download_thread.is_alive():
                if not clear_running:
                    return
                download_thread.stop()
                while download_thread.is_alive(): 
                    pass
        self._download_store.remove(iter)

    def _remove_selected(self):
        selection = self._download_view.get_selection()

        row_list = selection.get_selected_rows()[1]
        row_list.reverse()
        for row in row_list:
            iter = self._download_store.get_iter(row)
            self._remove_item(iter)

    def _get_filename(self, iter):
        return self._download_store.get_value(iter, 3)

    def _get_uri(self, iter):
        return self._download_store.get_value(iter, 4)

    def _set_filename(self, iter, filename):
        glib.idle_add(self._download_store.set_value, iter, 3, filename)

    def _set_uri(self, iter, uri):
        glib.idle_add(self._download_store.set_value, iter, 4, uri)
    
    def _set_progress(self, progress, iter):
        if int(float(progress)) != self._download_store.get_value(iter, 0):
            glib.idle_add(self._download_store.set_value, iter, 0, 
                    int(float(progress)))
        uri = self._get_uri(iter)
        download_thread = self._thread_dict.get(uri, None)
        
        total_size = download_thread.get_total_size()
        completed_size = download_thread.get_completed_size()
        self._set_size(total_size, 1, iter)
        self._set_size(completed_size, 2, iter)
    
    def _set_size(self, size, column, iter):
        size_list = ['B', 'KB', 'MB', 'GB', 'TB']
        count = 0
        while size > 1024:
            size /= 1024.0
            count += 1
        size_string = '%.*f %s' % (count, size, size_list[count])
        if size_string != self._download_store.get_value(iter, column):
            glib.idle_add(self._download_store.set_value, iter, column, 
                    size_string)

    def _clipboard_owner_change(self, clipboard, event):
        """ _clipboard_owner_changed -> Enable/disable the add uri menu item
        depending on if there is text in the clipboard.

        """

        # Enable/Disable the add_uri_item based on whether there is text 
        # in the clipboard either PRIMARY or CLIPBOARD
        self._add_uri_item.set_sensitive(
                clipboard.wait_is_text_available())
        
    def add_download(self, uri, filename=None, start=False):
        if not filename:
            filename = uri
        match = self._movie_pat.search(filename)
        if match:
            # Don't show save dialog for video downloads
            out_filename = match.groups()[0]
        else:
            save_dialog = SaveDialog(filename, self._current_folder)
            out_filename = save_dialog.run()
            self._current_folder = save_dialog.get_folder()
        if out_filename:
            iter = self._download_store.append((0, '0 B', '0 B', 
                out_filename, uri))

            # Scroll so the latest download is showing.
            self._download_view.scroll_to_cell(
                    (len(self._download_store) - 1,))
            if start:
                self._start_download(iter)
            return True
        else:
            return False

    def stop_all(self):
        for row in self._download_store:
            iter = row.iter
            self._remove_item(iter)
        self._aria_server.stop()
    
    def set_icon(self, icon_name):
        self._icon.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)

    def get_icon(self):
        return self._icon

    def get_title(self):
        return self._title

    def close(self):
        return False

class Aria2cServer(object):
    """ Starts aria2c in xml-rpc mode """

    def __init__(self, username=None, passwd=None, port=None):
        """ Aria2cServer() -> Object to start and stop 
        aria2c xml-rpc server """

        if not port:
            port = self._determine_port(6800)

        if not username:
            username = os.getenv('USER')

        if not passwd:
            passwd = self._gen_passwd(20)

        args_dict = {'username':username, 'passwd':passwd, 'port':port}
        self._xml_rpc_uri = 'http://%(username)s:%(passwd)s@127.0.0.1:%(port)s/rpc' % args_dict

        aria2c_exec = subprocess.Popen(['which', 'aria2c'], 
                stdout=subprocess.PIPE).communicate()[0].strip()
        self._aria2c_args = [
                aria2c_exec, 
                '--summary-interval=0', 
                '--enable-xml-rpc', 
                '--xml-rpc-listen-port=%s' % port, 
                '--xml-rpc-user=%s' % username, 
                '--xml-rpc-passwd=%s' % passwd,
                '--file-allocation=none'
                ]
        self._aria2c_proc = None

    def start(self):
        """ start() -> starts aria2c xml-rpc server """

        if not self._aria2c_proc:
            self._aria2c_proc = subprocess.Popen(self._aria2c_args, 
                    stdout=subprocess.PIPE)
        return True

    def stop(self, wait=False):
        """ stop() -> stops aria2c xml-rpc server """

        if self._aria2c_proc:
            self._aria2c_proc.terminate()
            if wait:
                self._aria2c_proc.wait()
            self._aria2c_proc = None
        return True

    def is_running(self):
        """ is_running() -> Returns True if server is running """

        return (self._aria2c_proc != None)

    def get_uri(self):
        """ get_uri() -> Returns xml-rpc server uri """

        return self._xml_rpc_uri

    def get_pid(self):
        """ get_pid() -> Returns the servers pid. """

        if self._aria2c_proc:
            return self._aria2c_proc.pid
        else:
            return None

    def _get_allready_running(self):
        """ returns allready running information """

        ps_cmd = subprocess.Popen(['ps', 'aux'], 
                stdout=subprocess.PIPE).communicate()[0].strip()
        aria_regex = re.compile(r'(aria2c.*)')
        match = aria_regex.search(ps_cmd)

        if match:
            aria_cmd = match.groups()[0]
            aria_user_regex = re.compile(r'xml-rpc-user=(\w*)')
            aria_pas_regex = re.compile(r'xml-rpc-passwd=(\w*)')
            match = aria_pas_regex.search(aria_cmd)
            if match:
                passwd = match.groups()[0]
            match = aria_user_regex.search(aria_cmd)
            if match:
                username = match.groups()[0]

        return match

    def _determine_port(self, start_port):
        """ _determine_port(start_port) -> Internal function to determine
        what port is available, staring at start_port """

        port = start_port
        while True:
            lsof_out = subprocess.Popen(['lsof', '-i', ':%s' % port], 
                    stdout=subprocess.PIPE).communicate()[0].strip()
            if lsof_out:
                port += 1
            else:
                break
        return port

    def _gen_passwd(self, length):
        """ _gen_passwd(length) -> Internal function to generate a 
        password of length length """

        chars = string.letters + string.digits + '_'
        passwd_list = []
        for i in xrange(length):
            passwd_list.append(chars[random.randrange(0, len(chars))])
        return ''.join(passwd_list)

class Aria2cClient(threading.Thread):
    """ Connects to aria2c xml-rpc server and uses it to download files """

    def __init__(self, uri, filename, progress_bar, server_uri):
        """ Aria2cClient(uri, filename, progress_bar, server_uri) ->
        uri - uri to download
        filename - file to save uri to
        progress_bar - progress_bar class to update
        server_uri - xml-rpc server to connect to """

        super(Aria2cClient, self).__init__()

        self._progress_bar = progress_bar
        self._uri = uri
        self._filename = filename
        self._server_uri = server_uri

        if filename:
            self._options = {'out' : os.path.relpath(self._filename)}
        else:
            self._options = None

        self._update_event = None
        self._is_alive = False

        self._aria2c = None
        self._gid = None
        self._progress = 0
        self._status = None
        self._total_size = 0
        self._completed_size = 0

    def run(self):
        """ start() -> Starts download """

        try:
            if not self._aria2c:
                self._aria2c = xmlrpclib.ServerProxy(self._server_uri)

            if self._options:
                self._gid = self._aria2c.aria2.addUri([self._uri], 
                        self._options)
            else:
                self._gid = self._aria2c.aria2.addUri([self._uri])
        except:
            return False

        if self._gid:
            self._is_alive = True
            while self._is_alive:
                self._update()
                time.sleep(.125)
            try:
                self._aria2c.aria2.remove(self._gid)
            except:
                pass

            self._finish()

        return True

    def stop(self):
        """ stop() -> Stops and cleans up download """

        if self._is_alive:
            self._is_alive = False

    def is_alive(self):
        """ is_alive() -> Returns True if download is active """

        return self._is_alive

    def get_total_size(self):
        """ get_total_size() -> Returns total size of download """

        if int(self._total_size) == 0:
            self._total_size = os.path.getsize(self._filename)
        return int(self._total_size)

    def get_completed_size(self):
        """ get_completed_size() -> Returns completed size of download """

        if int(self._completed_size) == 0:
            self._completed_size = os.path.getsize(self._filename)
        return int(self._completed_size)

    def _finish(self):
        """ _finish() -> Internal function to cleanup when download 
        is stopped or fineshes. """

        self._gid = None
        self._is_alive = False
        try:
            self._aria2c.aria2.purgeDownloadResult()
        except:
            pass

    def _set_progress(self, progress):
        """ _set_progress(progress) -> Internal function to update 
        progress class """

        self._progress_bar.set_fraction(progress/100.0)
        self._progress_bar.set_text('%f%%' % progress)
        self._progress = progress

    def _get_progress(self):
        """ _get_progress() -> Internal function returns progress """
        return self._progress

    def _update(self):
        """ _update() -> Internal function to update progress and 
        cleanup when done """

        try:
            status = self._aria2c.aria2.tellStatus(self._gid)
        except:
            return False

        self._status = status
        #print("%s %s" % (strftime('%h %e %H:%M:%S'), status['status']))
        if status['status'] == 'active':
            if float(status.get('totalLength', 0)) > 0:
                self._total_size = status['totalLength']
                self._completed_size = status['completedLength']
                progress = float(status['completedLength'])/float(status['totalLength'])*100
                self._set_progress(float(progress))
            return True
        else:
            self._completed_size = self._total_size
            self._set_progress(100)
            self._finish()

class Aria2cDownload(threading.Thread):
    """ Object to start and stop downloads using aria2c. 
    
    """
    
    def __init__(self, uri, filename, progress_bar):
        """ Aria2cDownload(uri, filename, progress_bar) ->
        uri - uri to download
        filename - file to save uri to
        progress_bar - progress bar class to update 
        
        """

        super(Aria2cDownload, self).__init__()

        self._progress_bar = progress_bar
        self._uri = uri
        self._filename = filename

        # regular expression to check for (1-3 digits %)
        self._progress_regex = re.compile(r'\(([0-9]{1,3})%\)')

        self._size_regex = re.compile(
                r'SIZE:(\d*\.?\d?)[a-zA-Z]*\/(\d*\.?\d?)'
                )
        self._size_progress_regex = re.compile(
                r'SIZE:(\d*,?\d*\.?\d?)([a-zA-Z]*)\/(\d*,?\d*\.?\d?)([a-zA-Z]*)\((\d{1,3})%\)'
                )

        self._aria2c_exec = subprocess.Popen(['which', 'aria2c'], 
                stdout=subprocess.PIPE).communicate()[0].strip()
        self._aria2c_args = [
                self._aria2c_exec, 
                '--summary-interval=0', 
                '--file-allocation=none',
                '-c',
                self._uri, 
                '-o', os.path.relpath(self._filename)
                ]
        self._aria2c_proc = None
        self._aria2c_poll = None
        self._update_event = None
        self._is_alive = False
        self._total_size = 0
        self._completed_size = 0

    def run(self):
        """ start() -> Start the download process.
        
        """

        self._aria2c_proc = subprocess.Popen(self._aria2c_args, 
                stdout=subprocess.PIPE)

        # Set process stdout to nonblocking mode.
        fcntl(self._aria2c_proc.stdout, F_SETFL, 
                fcntl(self._aria2c_proc.stdout, F_GETFL)| os.O_NONBLOCK)

        # Setup poll object on stdout of process.
        self._aria2c_poll = poll()
        self._aria2c_poll.register(self._aria2c_proc.stdout, POLLIN)
        
        # Start update loop.
        self._is_alive = True
        while self._is_alive and not self._aria2c_proc.poll():
            self._update()
            time.sleep(.125)
        self._is_alive = False

    def stop(self):
        """ stop() -> stop download """

        # If download is active stop it.
        if self._is_alive:  
            self._is_alive = False
            # Terminate the download process.
            try:
                self._aria2c_proc.terminate()
                self._aria2c_proc.wait()
            except OSError:
                pass

    def is_alive(self):
        """ is_alive() -> returns true if download is active """

        return self._is_alive

    def get_total_size(self):
        """ get_total_size() -> Returns total size of download """

        return float(self._total_size)

    def get_completed_size(self):
        """ get_completed_size() -> Returns completed size of download """

        return float(self._completed_size)

    def _set_progress(self, progress):
        """ _set_progress(progress) -> Internal function to update 
        progress_bar.
        
        """

        self._progress_bar.set_fraction(progress/100.0)
        self._progress_bar.set_text('%f%%' % progress)

    def _get_progress(self):
        """ _get_progress() -> Internal function to get current progress. 
        
        """

        return self._progress_bar.get_fraction()

    def _update(self):
        """ _update() -> Internal function to update progress from
        aria2c stdout PIPE """

        #print("%s updating" % strftime('%h %e %H:%M:%S'))
        # Poll with timeout of 1 second.
        self._aria2c_poll.poll(1)
        try:
            # Try to read the output.
            data = self._aria2c_proc.stdout.readline().strip()

            # if the download is active update progress
            if data.startswith('[#1'):
                match = self._size_progress_regex.search(data)
                if match:
                    self._completed_size, complete_s, self._total_size, total_s, progress = match.groups()
                    s_list = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
                    self._completed_size = float(self._completed_size.replace(',', ''))
                    self._total_size = float(self._total_size.replace(',', ''))
                    self._completed_size *= (1024 ** s_list.index(complete_s))
                    self._total_size *= (1024 ** s_list.index(total_s))
                    if int(self._total_size) == 0:
                        self._total_size = os.path.getsize(self._filename)
                    if int(self._completed_size) == 0:
                        self._completed_size = os.path.getsize(self._filename)
                    self._set_progress(float(progress))
            elif data.startswith('(OK):'):       
                # Download is finished.
                if int(self._total_size) == 0:
                    self._total_size = os.path.getsize(self._filename)
                self._completed_size = self._total_size
                self._set_progress(100)
                self._aria2c_proc.wait()
                self._is_alive = False              
                # Return False so update event will end.
                return False            
        except:
            pass
        return True

class URLOpenerResume(urllib.FancyURLopener):
    """ Sub-class to overrite rror 206 so we can resume """

    def http_error_206(self, url, fp, errcode, errmsg, headers, data=None):
        pass

class DownloadCanceled(Exception):pass

class Download(threading.Thread):
    def __init__(self, url, filename, progress=None):
        super(Download, self).__init__()
        self._url = url
        self._filename = filename
        self._progress = progress
        self._stopped = False
        self._grabber = URLOpenerResume()

        self._total_size = 0
        self._completed_size = 0

    def get_total_size(self):
        """ get_total_size() -> Returns total size of download """

        return int(self._total_size)

    def get_completed_size(self):
        """ get_completed_size() -> Returns completed size of download """

        return int(self._completed_size)

    def _update(self, count, blockSize, totalSize):
        try:
            fraction = (float(count) * blockSize) / totalSize
            self._total_size = totalSize
            self._completed_size = float(count) * blockSize
            if self._completed_size > self._total_size:
                self._completed_size = self._total_size
        except Exception as e:
            print("Error downloading: %s" % e.message)
            raise DownloadCanceled()
        if fraction > 1:
            fraction = 1.0
        if self._progress:
            self._progress.set_fraction(fraction)
            self._progress.set_text('%d' % (fraction*100))

        if self._stopped:
            if self._progress:
                self._progress.set_fraction(0.0)
            print("Stopping Download...")
            raise DownloadCanceled()

    def stop(self):
        self._stopped = True

    def run(self):
        try:
            print("Attempting to download: %s to %s" % (self._url, 
                self._filename))
            if self._stopped:
                return
            if os.path.exists(self._filename):
                ret_size = os.path.getsize(self._filename)
                self._grabber.addheader("Range", "bytes=%d-" % (ret_size))
 
            self._grabber.retrieve(self._url, self._filename, 
                    reporthook=self._update)
            print("Finished downloading %s to %s" % (self._url, 
                self._filename))
            self._progress.set_fraction(1.0)
        except DownloadCanceled:
            print("Download Canceled")
            return

class BarProgress(object):
    """ Provide a bar Progress """

    def __init__(self, progress_func, progress_bar, fraction_func=None):
        self._fraction = 0.0
        self._text = None
        self._progress_func = progress_func
        self._progress_bar = progress_bar

    def set_text(self, text):
        self._text = text
        progress = text.strip('%')
        self._progress_func(int(float(progress)), self._progress_bar)

    def set_fraction(self, fraction):
        self._fraction = fraction

    def get_fraction(self):
        return self._fraction

class TempDownload(threading.Thread, gobject.GObject):
    """ TempDownload -> Start a new thread to download a file and emit a 
    'download-finished' signal when done.

    """

    __gsignals__ = {
            'download-finished' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
            }

    def __init__(self, uri, filename):
        """ TempDownload -> Temp file download thread.

        """

        threading.Thread.__init__(self)
        gobject.GObject.__init__(self)
        self._uri = uri
        self._filename = filename
        self._grabber = urllib.FancyURLopener()

    def run(self):
        self._grabber.retrieve(self._uri, self._filename)
        self.emit('download-finished', self._filename)

class FaviconDownload(threading.Thread, gobject.GObject):
    """ FaviconDownload -> Start a new thread to download a favicon and emit a 
    'download-finished' signal when done.

    """

    __gsignals__ = {
            'download-finished' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_STRING, gobject.TYPE_STRING, 
                    gobject.TYPE_PYOBJECT)),
            }

    def __init__(self, uri_tup, filename):
        """ FaviconDownload -> Favicon download thread.

        """

        threading.Thread.__init__(self)
        gobject.GObject.__init__(self)
        self._uri_tup = uri_tup
        self._filename = filename
        self._grabber = urllib.FancyURLopener()

    def run(self):
        # Try all icon uris
        for uri in self._uri_tup:
            try:    
                print("Favicon downloader: trying icon: %s" % uri)
                # Save icon to 'favicon_file'
                self._grabber.retrieve(uri, self._filename)

                pixbuf_icon = gtk.gdk.pixbuf_new_from_file(self._filename)
                pixbuf_icon = pixbuf_icon.scale_simple(16, 16, 
                        gtk.gdk.INTERP_BILINEAR)

                # If this icon succeeds then exit don't try the next
                break
            except:
                print("Favicon downloader: icon failed: %s" % uri)
                # The uri failed to load a valid icon
                # so use the default 'text-html' icon
                icon_theme = gtk.icon_theme_get_default()
                pixbuf_icon = icon_theme.load_icon('text-html', 
                        gtk.ICON_SIZE_MENU, gtk.ICON_LOOKUP_USE_BUILTIN)

        self.emit('download-finished', uri, self._filename, pixbuf_icon)
