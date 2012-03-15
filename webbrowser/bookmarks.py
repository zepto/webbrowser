# This file is part of browser, and contains the bookmark classes.
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

""" A bunch of objects to manipulate and use xbel bookmark files.

Bookmarks - A bookmark object that manipulates xbel bookmark files.
BookmarksMenu - A bookmark menu that uses the Bookmarks object to read and 
                write the bookmarks.
FolderSelect -> Provides a dialog box for selecting and making new folders 
                and bookmarks.
NameEntry -> A dialog for editing the name an uri of a bookmark.

"""

import os
import codecs
import threading
import urllib2
import re
import shutil
from xml.dom.minidom import parse, parseString

import gtk
import gobject
import pango
import glib
from lxml import etree

from defaults import APP_NAME

class Bookmarks(object):

    def __init__(self, filename):
        empty_bookmarks = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xbel PUBLIC "+//IDN python.org//DTD XML Bookmark Exchange Language 1.0//EN//XML" "http://www.python.org/topics/xml/dtds/xbel-1.0.dtd">
<xbel version="1.0" xmlns:browser="lime.tree">
</xbel>"""

        self._filename = filename
        if os.path.isfile(filename):
            self._tree = etree.parse(filename)
        else:
            root = etree.fromstring(empty_bookmarks)
            self._tree = etree.ElementTree(root)

        self._root = self._tree.getroot()

        self._alpha_pat = re.compile('[^a-zA-Z]')
        self._space_pat = re.compile(' +')

    def update(self):
        self._tree = etree.parse(self._filename)

    def create_title(self, text):
        title = self._root.makeelement(u'title', attrib={})
        title.text = text.decode()
        title.tail = u'\n'
        return title

    def create_bookmark(self, title, uri):
        if not uri:
            uri = 'about:blank'
        link = {'href': uri.decode()}
        bookmark = self._root.makeelement(u'bookmark', attrib=link)
        bookmark.tail = u'\n'
        bookmark.append(self.create_title(title))
        bookmark.text = u'\n'
        return bookmark

    def create_folder(self, title):
        folder = self._root.makeelement(u'folder', attrib={})
        folder.text = u'\n'
        folder.append(self.create_title(title))
        folder.tail = u'\n'
        return folder

    def add_bookmark(self, title, uri, parent):
        bookmark = self.create_bookmark(title, uri)
        self.append_bookmark(parent, bookmark)
        return bookmark

    def add_folder(self, title, parent):
        folder = self.create_folder(title)
        self.append_folder(parent, folder)
        return folder

    def _istype(self, element, type):
        if element.tag in type:
            return True
        else:
            return False

    def isbookmark(self, element):
        return self._istype(element, u'bookmark')

    def isfolder(self, element):
        return self._istype(element, u'folder')

    def move_element(self, element, dest):
        self.append_bookmark(dest, self.remove_bookmark(element))
        return element

    move_bookmark = move_element
    move_folder = move_element

    def remove_element(self, element):
        element.getparent().remove(element)
        return element
    
    remove_bookmark = remove_element
    remove_folder = remove_element
   
    def rename_element(self, element, text):
        title = self.get_title(element)
        self.set_title_text(title, text)
        return element

    rename_bookmark = rename_element
    rename_folder = rename_element

    def append_element(self, parent, element):
        parent.append(element)
        return element
    
    append_folder = append_element
    append_bookmark = append_element

    def insert_element(self, parent, prev_item, element):
        parent.insert(parent.index(prev_item), element)
        return element

    insert_bookmark = insert_element
    insert_folder = insert_element

    def edit_bookmark(self, bookmark, text, uri):
        title = self.get_title(bookmark)
        self.set_title_text(title, text)
        self.set_uri(bookmark, uri)
        return bookmark

    def set_title_text(self, title, text):
        title.text = text.decode()
        return title

    def set_uri(self, bookmark, uri):
        bookmark.attrib[u'href'] = uri.decode()

    def get_parent(self, element):
        return element.getparent()

    def get_uri(self, bookmark):
        return bookmark.get(u'href', 'about:blank')

    def get_title(self, node):
        title = node.find('title')
        if title is None:
            title = self.create_title('Blank')
        return title

    def get_title_text(self, element):
        return element.findtext('title')

    def get_folder_by_title(self, foldername):
        for folder in self._root.findall('folder'):
            if folder.findtext('title') == foldername:
                return folder
        return self.create_folder(foldername)

    def get_top_parent(self):
        return self._root

    def get_element_list_sorted(self, parent, 
            element_type=[u'folder', u'bookmark'], reverse=False):
        elements_list = self.get_element_list(parent, element_type)
        elements_list.sort(cmp=self._element_sort, reverse=reverse)
        return elements_list

    def get_bookmark_list_sorted(self, parent, reverse=False):
        return self.get_element_list_sorted(parent, u'bookmark', 
                reverse=reverse)

    def get_folder_list_sorted(self, parent, reverse=False):
        return self.get_element_list_sorted(parent, u'folder', 
                reverse=reverse)

    def get_element_list(self, parent, name):
        if type(name) != list:
            name = [name]
        element_list = []
        for tag_name in name:
            element_list.extend(parent.findall(tag_name))
        return element_list

    def get_all_bookmarks_list(self):
        return self._root.findall(u'.//bookmark')

    def get_bookmark_list(self, parent):
        return self.get_element_list(parent, u'bookmark')

    def get_folder_list(self, parent):
        return self.get_element_list(parent, u'folder')

    def get_element_name(self, element):
        return element.tag

    def iter_elements_type(self, parent, name):
        for element in parent.findall(name):
            yield(element)

    def iter_bookmarks(self, parent):
        """ iter_bookmarks(parent) -> Returns an iter of all the bookmarks in
        parent.

        """

        return self.iter_elements_type(parent, u'bookmark')

    def iter_folders(self, parent):
        """ iter_folders(parent) -> Returns an iter of all the folders in 
        parent.

        """

        return self.iter_elements_type(parent, u'folder')

    def _clean_title(self, title, *args):
        """ _clean_title(title, *args) -> Clean the title text using the 
        patterns in *args.  

        """

        temp_title = title
        for pat in args:
            temp_title = pat.sub(' ', temp_title)
        return temp_title.strip()

    def _element_sort(self, e1, e2):
        """ _element_sort(e1, e2) -> A sort method for the sort function.
        Use the element titles to sort them.

        """

        if (self.isfolder(e1) and self.isfolder(e2)) or (self.isbookmark(e1) 
                and self.isbookmark(e2)):
            # Both elements are the same type so sort them by their title.
            # We want to sort by the letters in the title, so we remove 
            # everything else.
            title1 = self._clean_title(self.get_title_text(e1).lower(), 
                    self._alpha_pat, self._space_pat)
            title2 = self._clean_title(self.get_title_text(e2).lower(), 
                    self._alpha_pat, self._space_pat)
            if title1 > title2:
                return 1
            elif title1 == title2:
                return 0
            else:
                return -1
        else:
            # Sort folders above bookmarks.
            if self.isfolder(e1):
                return -1
            else:
                return 1

    def save_bookmarks(self, filename):
        if os.path.isfile(filename):
            shutil.move(filename, '%s.bak' % filename)
        self._tree.write(filename, encoding='UTF-8', xml_declaration=True)

class OldBookmarks(object):

    def __init__(self, filename):
        empty_bookmarks = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xbel PUBLIC "+//IDN python.org//DTD XML Bookmark Exchange Language 1.0//EN//XML" "http://www.python.org/topics/xml/dtds/xbel-1.0.dtd">
<xbel version="1.0" xmlns:browser="lime.tree">
</xbel>"""

        self._filename = filename
        if os.path.isfile(filename):
            self._dom = parse(filename)
        else:
            self._dom = parseString(empty_bookmarks)

        self._alpha_pat = re.compile('[^a-zA-Z]')
        self._space_pat = re.compile(' +')

    def update(self):
        self._dom = parse(self._filename)

    def create_title(self, text):
        title = self._dom.createElement(u'title')
        title.appendChild(self._dom.createTextNode(text.decode()))
        return title

    def create_bookmark(self, title, uri):
        bookmark = self._dom.createElement(u'bookmark')
        bookmark.appendChild(self._dom.createTextNode(u'\n'))
        if not uri:
            uri = 'about:blank'
        bookmark.setAttribute(u'href', uri.decode())
        bookmark.appendChild(self.create_title(title))
        bookmark.appendChild(self._dom.createTextNode(u'\n'))
        return bookmark

    def create_folder(self, title):
        folder = self._dom.createElement(u'folder')
        folder.appendChild(self._dom.createTextNode(u'\n'))
        folder.appendChild(self.create_title(title))
        folder.appendChild(self._dom.createTextNode(u'\n'))
        return folder

    def add_bookmark(self, title, uri, parent):
        bookmark = self.create_bookmark(title, uri)
        self.append_bookmark(parent, bookmark)
        return bookmark

    def add_folder(self, title, parent):
        folder = self.create_folder(title)
        self.append_folder(parent, folder)
        return folder

    def _istype(self, element, type):
        if element.nodeName in type:
            return True
        else:
            return False

    def isbookmark(self, element):
        return self._istype(element, u'bookmark')

    def isfolder(self, element):
        return self._istype(element, u'folder')

    def move_element(self, element, dest):
        self.append_bookmark(dest, self.remove_bookmark(element))
        return element

    move_bookmark = move_element
    move_folder = move_element

    def remove_element(self, element):
        nextblank = element.nextSibling
        if nextblank.nodeName == '#text':
            nextblank.parentNode.removeChild(nextblank)
        element.parentNode.removeChild(element)
        return element
    
    remove_bookmark = remove_element
    remove_folder = remove_element
   
    def rename_element(self, element, text):
        title = self.get_title(element)
        self.set_title_text(title, text)
        return element

    rename_bookmark = rename_element
    rename_folder = rename_element

    def append_element(self, parent, element):
        parent.appendChild(element)
        parent.appendChild(self._dom.createTextNode(u'\n'))
        return element
    
    append_folder = append_element
    append_bookmark = append_element

    def insert_element(self, parent, prev_item, element):
        parent.insertBefore(prev_item, element)
        parent.insertBefore(prev_item, self._dom.createTextNode(u'\n'))
        return element

    insert_bookmark = insert_element
    insert_folder = insert_element

    def edit_bookmark(self, bookmark, text, uri):
        title = self.get_title(bookmark)
        self.set_title_text(title, text)
        self.set_uri(bookmark, uri)
        return bookmark

    def set_title_text(self, title, text):
        text_element = title.childNodes[0]
        text_element.replaceWholeText(text.decode())
        return title

    def set_uri(self, bookmark, uri):
        bookmark.setAttribute(u'href', uri.decode())

    def get_parent(self, element):
        return element.parentNode

    def get_uri(self, bookmark):
        if bookmark.hasAttribute(u'href'):
            return bookmark.getAttribute(u'href')
        else:
            return 'about:blank'

    def get_title(self, node):
        for e in node.childNodes:
            if e.nodeName == 'title':
                return e
        return self.create_title('Blank')

    def get_title_text(self, element):
        return self.get_title(element).childNodes[0].nodeValue.strip()

    def get_folder_by_title(self, foldername):
        for folder in self._dom.getElementsByTagName('folder'):
            title = self.get_title_text(folder)
            if title == foldername:
                return folder
        return self.create_folder(foldername)

    def get_top_parent(self):
        return self._dom.childNodes[1]

    def get_element_list_sorted(self, parent, 
            element_type=[u'folder', u'bookmark'], reverse=False):
        elements_list = self.get_element_list(parent, element_type)
        elements_list.sort(cmp=self._element_sort, reverse=reverse)
        return elements_list

    def get_bookmark_list_sorted(self, parent, reverse=False):
        return self.get_element_list_sorted(parent, u'bookmark', 
                reverse=reverse)

    def get_folder_list_sorted(self, parent, reverse=False):
        return self.get_element_list_sorted(parent, u'folder', reverse=reverse)

    def get_element_list(self, parent, name):
        element_list = []
        for element in self.iter_elements(parent):
            if element.nodeName in name:
                element_list.append(element)
        return element_list

    def get_all_bookmarks_list(self):
        return self._dom.getElementsByTagName(u'bookmark')

    def get_bookmark_list(self, parent):
        return self.get_element_list(parent, u'bookmark')

    def get_folder_list(self, parent):
        return self.get_element_list(parent, u'folder')

    def get_element_name(self, element):
        return element.nodeName

    def iter_elements_type(self, parent, name):
        for element in self.iter_elements(parent):
            if element.nodeName in name:
                yield(element)

    def iter_bookmarks(self, parent):
        return self.iter_elements_type(parent, u'bookmark')

    def iter_folders(self, parent):
        return self.iter_elements_type(parent, u'folder')

    def iter_elements(self, parent):
        for element in parent.childNodes:
            yield(element)

    def _clean_title(self, title, *args):
        temp_title = title
        for pat in args:
            temp_title = pat.sub(' ', temp_title)
        return temp_title.strip()

    def _element_sort(self, e1, e2):
        if (self.isfolder(e1) and self.isfolder(e2)) or (self.isbookmark(e1) 
                and self.isbookmark(e2)):
            title1 = self._clean_title(self.get_title_text(e1).lower(), 
                    self._alpha_pat, self._space_pat)
            title2 = self._clean_title(self.get_title_text(e2).lower(), 
                    self._alpha_pat, self._space_pat)
            if title1 > title2:
                return 1
            elif title1 == title2:
                return 0
            else:
                return -1
        else:
            if self.isfolder(e1):
                return -1
            else:
                return 1

    def save_bookmarks(self, filename):
        if os.path.isfile(filename):
            shutil.move(filename, '%s.bak' % filename)
        bookmark_file = codecs.open(filename, 'wb', 'utf-8')
        bookmark_file.write(self._dom.toxml(encoding='UTF-8'))
        bookmark_file.stream.flush()
        bookmark_file.stream.close()

class BookmarksMenu(gtk.Menu):

    __gsignals__ = {
            'bookmark-button-release' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, 
                    gobject.TYPE_STRING)),
            'new-bookmark' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, ()),
            'bookmark-tabs' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT)),
            'folder-as-tabs' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT, 
                    gobject.TYPE_PYOBJECT)),
            }

    def __init__(self, filename='bookmarks.xbel', profile='default'):
        super(BookmarksMenu, self).__init__()

        self._bookmarks_filename = '%s/%s/%s/%s' % \
                (glib.get_user_config_dir(), APP_NAME, profile, filename)
        self._bookmarks = None
        self._completion_model = gtk.ListStore(str, str)

    def _update_bookmarks(self):
        self._bookmarks.save_bookmarks(self._bookmarks_filename)
        self._build_bookmark_menu()
        self.setup_completion_model()

    def _build_bookmark_menu(self):
        build_thread = threading.Thread(target=self.do_build_bookmark_menu)
        build_thread.daemon = True
        build_thread.start()

    def setup_completion_model(self):
        model_thread = threading.Thread(target=self.do_setup_completion_model)
        model_thread.daemon = True
        model_thread.start()

    def do_setup_completion_model(self):
        try:
            self._completion_model.clear()
            for title, uri in self.get_all_bookmarks_list():
                scheme = '%s://' % urllib2.urlparse.urlsplit(uri).scheme
                self._completion_model.append(
                        [uri.replace(scheme, '', 1).replace('www.', '', 1), uri])
                self._completion_model.append([title, uri])
        except:
            pass
    
    def get_completion_model(self):
        return self._completion_model

    def _position_func(self, menu, user_data):
        offset = 22
        return (int(user_data.x_root - user_data.x), 
                int(user_data.y_root - user_data.y) + offset, False)

    def popup_menu(self, event):
        if not self._bookmarks:
            self._bookmarks = Bookmarks(self._bookmarks_filename)
            self._build_bookmark_menu()

        self.popup(None, None, self._position_func, event.button, 
                event.time, event)

    def _folder_press(self, folder_item, event, folder): 
        if event.button == 3:

            right_click_menu = gtk.Menu()
            menu_tup = (
                    ('gtk-edit', '_Edit Folder', 'Edit Folder', 
                        self._edit_folder, folder),
                    gtk.SeparatorMenuItem(),
                    ('gtk-delete', '_Delete Folder', 'Delete Folder', 
                        self._delete_folder, folder),
                    )

            for item in menu_tup:
                if type(item) == tuple:
                    menu_item = self._make_menu_item(*item)
                else:
                    menu_item = item
                right_click_menu.add(menu_item)
            
            right_click_menu.show_all()
            right_click_menu.popup(None, None, None, event.button, 
                    event.time, None)
            return True

    def _open_new_tab(self, menu_item, event, bookmark):
        event.button = 2
        self._bookmark_release(menu_item, event, bookmark)

    def _bookmark_release(self, menu_item, event, bookmark): 
        if menu_item.get_data('drag'):
            return

        uri = self._bookmarks.get_uri(bookmark)
        if event.button == 3:
            right_click_menu = gtk.Menu()

            menu_tup = (
                    ('gtk-open', '_Open', 'Open Bookmark', 
                        lambda *args: self._bookmark_release(*args), 
                        bookmark),
                    ('tab-new', '_Open in new Tab', 
                        'Open Bookmark in a New Tab', 
                        self._open_new_tab, bookmark),
                    gtk.SeparatorMenuItem(),
                    ('gtk-edit', '_Edit Bookmark', 'Edit Bookmark', 
                        self._edit_bookmark, bookmark),
                    ('gtk-delete', '_Delete Bookmark', 'Delete Bookmark', 
                        self._delete_bookmark, bookmark),
                    )

            for item in menu_tup:
                if type(item) == tuple:
                    menu_item = self._make_menu_item(*item)
                else:
                    menu_item = item
                right_click_menu.add(menu_item)
            
            right_click_menu.show_all()
            right_click_menu.popup(None, None, None, event.button, 
                    event.time, None)
            return True
        else:
            self.popdown()
            self.emit('bookmark-button-release', event, uri)

    def _delete_bookmark(self, delete_item, event, bookmark):
        self.popdown()
        delete_item.parent.popdown()
        self._bookmarks.remove_bookmark(bookmark)
        self._update_bookmarks()

    _delete_folder = _delete_bookmark

    def _edit_folder(self, edit_item, event, folder):
        """ _edit_folder -> Opens a dialog where the user can rename and move
        the selected folder.

        """

        # First hide the popup menus.
        self.popdown()
        edit_item.parent.popdown()

        # Get the current name and parent of the folder.
        name = self._bookmarks.get_title_text(folder)
        parent_folder = self._bookmarks.get_parent(folder)

        # Setup and run the dialog.
        result_dict = FolderSelect.folder_select('Edit Folder', 'gtk-edit', 
                self._bookmarks, name, parent_folder, skip=folder)

        if result_dict['response'] == gtk.RESPONSE_OK:
            # Get the names.
            dest_folder = result_dict['dest_folder']
            new_name = result_dict['name']

            # Only move the folder if the destination is different than the 
            # old parent.
            if dest_folder != folder and dest_folder != parent_folder:
                self._bookmarks.move_folder(folder, dest_folder)

            # Only rename the folder if the new name is different than the 
            # old.
            if new_name != name:
                self._bookmarks.rename_element(folder, new_name)

            # Save the bookmarks and update the menu.
            self._update_bookmarks()
        elif result_dict['folder_created']:
            # If a new folder was created then update the bookmarks.
            self._update_bookmarks()

    def _edit_bookmark(self, edit_item, event, bookmark):
        """ _edit_bookmark -> Opens a dialog where the user can rename, 
        change the uri, and move the selected bookmark.

        """

        # First hide the popup menus.
        self.popdown()
        edit_item.parent.popdown()

        # Get the current name and parent of the folder.
        name = self._bookmarks.get_title_text(bookmark)
        uri = self._bookmarks.get_uri(bookmark)
        parent_folder = self._bookmarks.get_parent(bookmark)

        # Setup and run the dialog.
        result_dict = FolderSelect.folder_select('Edit Bookmark', 'gtk-edit',
                self._bookmarks, name, parent_folder, uri)
        if result_dict['response'] == gtk.RESPONSE_OK:
            dest_folder = result_dict['dest_folder']
            new_name = result_dict['name']
            new_uri = result_dict['uri']

            # Only move the bookmark if the destination is different than the 
            # old parent.
            if dest_folder != parent_folder:
                self._bookmarks.move_bookmark(bookmark, dest_folder)

            # Only rename the folder if the new name is different than the 
            # old.
            if (new_name and new_uri) and (new_name != name or new_uri != uri):
                self._bookmarks.edit_bookmark(bookmark, new_name, new_uri)

            # Save the bookmarks and update the menu.
            self._update_bookmarks()
        elif result_dict['folder_created']:
            # If a new folder was created then update the bookmarks.
            self._update_bookmarks()

    def _add_bookmark_here(self, button, event, folder):
        title_uri_tup = self.emit('new-bookmark')
        if title_uri_tup:
            title, uri = title_uri_tup
            result_tup = NameEntry.name_entry('Bookmark Name',
                    'stock_add-bookmark', title, uri=uri)
            if result_tup:
                name, uri = (result_tup)
                if name:
                    self._bookmarks.add_bookmark(name, uri, folder)
                    self._update_bookmarks()

    def _add_folder_here(self, add_folder_item, event, parent_folder, 
            bookmark_tabs=False):
        add_folder_item.parent.popdown() 
        result_tup = NameEntry.name_entry('Enter Folder Name', 'folder-new', 
                'New Folder')
        if result_tup:
            folder_name, empty = result_tup
            if folder_name:
                new_folder = self._bookmarks.add_folder(folder_name, 
                        parent_folder)
                if bookmark_tabs:
                    self.emit('bookmark-tabs', new_folder, self._bookmarks)
                self._update_bookmarks()

    def _add_bookmark(self, add_bookmark_item, event):
        add_bookmark_item.parent.popdown()
        title_uri_tup = self.emit('new-bookmark')
        if title_uri_tup:
            title, uri = title_uri_tup
            self.new_bookmark(title, uri)

    def new_bookmark(self, title, uri):
        """ new_bookmark(title, uri) -> Let the user select a folder and 
        edit the name and uri of the new bookmark.

        """

        # Setup and run the dialog
        result_dict = FolderSelect.folder_select('New Bookmark', 
                'stock_add-bookmark',
                self._bookmarks, title, uri=uri)
        if result_dict['response'] == gtk.RESPONSE_OK:
            dest_folder = result_dict['dest_folder']
            new_name = result_dict['name']
            new_uri = result_dict['uri']
            self._bookmarks.add_bookmark(new_name, new_uri, dest_folder)
            self._update_bookmarks()
        elif result_dict['folder_created']:
            # If a new folder was created then update the bookmarks.
            self._update_bookmarks()

    def _open_folder_tabs(self, button, event, folder):
        self.emit('folder-as-tabs', event, folder, self._bookmarks)

    def get_all_bookmarks_list(self):
        if not self._bookmarks:
            self._bookmarks = Bookmarks(self._bookmarks_filename)
            self._build_bookmark_menu()

        for bookmark in self._bookmarks.get_all_bookmarks_list():
            yield (self._bookmarks.get_title_text(bookmark), 
                    self._bookmarks.get_uri(bookmark))

    def do_build_bookmark_menu(self):
        try:
            glib.idle_add(self.foreach, self.remove)

            self._make_folder_menu(self._bookmarks.get_top_parent())

            glib.idle_add(self._add_add_items, self._bookmarks.get_top_parent())

            glib.idle_add(self.show_all)
        except Exception as err:
            print("Error building menu: %s" % err)

    def _make_menu_item(self, icon_name, label_text, tooltip_text, 
            click_func, *user_args):
        icon = gtk.Image()
        icon.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)
        menu_item = gtk.ImageMenuItem()
        menu_item.set_image(icon)
        menu_item.set_label(label_text)
        menu_item.set_tooltip_text(tooltip_text)
        menu_item.set_use_underline(True)
        menu_item.connect('button-release-event', click_func, *user_args)

        return menu_item

    def _add_add_items(self, folder, menu=None):
        if not menu:
            menu = self

        separator_item = gtk.SeparatorMenuItem()
        menu.add(separator_item)

        item_list = [
                ('folder-open', '_Open Folder as Tabs', 
                    'Open all bookmarks in this folder as new tabs',
                    self._open_folder_tabs, folder),
                ('stock_add-bookmark', 'Add _Bookmark Here', 
                    'Bookmark current page to this folder',
                    self._add_bookmark_here, folder),
                ('folder-new', 'Add _Folder Here', 
                    'Create a new folder in this folder', 
                    self._add_folder_here, folder),
                ('folder-new', 'Bookmark _Tabs as Folder Here', 
                    'Create a new folder in this folder with bookmarks of all the tabs',
                    self._add_folder_here, folder, True),
                ]

        if folder != self._bookmarks.get_top_parent():
            ext_item_list = [
                    gtk.SeparatorMenuItem(),
                    ('gtk-edit', '_Edit Folder', 
                        'Rename the current folder',
                        self._edit_folder, folder),
                    ('gtk-delete', '_Delete Folder', 
                        'Delete the current folder',
                        self._delete_folder, folder),
                    ]
            item_list.extend(ext_item_list)
        else:
            accel_group = gtk.AccelGroup()
            menu.set_accel_group(accel_group)

            menu.prepend(gtk.SeparatorMenuItem())

            add_bookmark_item = self._make_menu_item('stock_add-bookmark', 
                    'Bookmark _This Page', 'Bookmark current page',
                    self._add_bookmark)

            add_bookmark_item.add_accelerator('activate', accel_group, 
                    gtk.gdk.keyval_from_name('D'), gtk.gdk.CONTROL_MASK, 
                    gtk.ACCEL_VISIBLE)
            menu.prepend(add_bookmark_item)

        for item in item_list:
            if type(item) == tuple:
                menu_item = self._make_menu_item(*item)
            else:
                menu_item = item
            menu.add(menu_item)


    def _make_folder_menu(self, folder):
        if folder != self._bookmarks.get_top_parent():
            menu = gtk.Menu()
        else:
            menu = self
        menuitem = None
        for element in self._bookmarks.get_element_list_sorted(folder): 
            element_name = self._bookmarks.get_element_name(element)
            if element_name == u'folder':
                menuitem = gtk.ImageMenuItem('gtk-directory')
                submenu = self._make_folder_menu(element)
                glib.idle_add(self._add_add_items, element, submenu)
                menuitem.set_submenu(submenu)
                menuitem.connect('button-press-event', 
                        self._folder_press, element)
            elif element_name == u'bookmark':
                icon = gtk.Image()
                icon.set_from_icon_name('text-html', gtk.ICON_SIZE_MENU)
                menuitem = gtk.ImageMenuItem('text-html')
                menuitem.set_image(icon)
                menuitem.set_tooltip_text(self._bookmarks.get_uri(element))
                menuitem.connect('drag-data-get', self._get_bookmark_data, element)
                menuitem.connect('drag-begin', lambda i, *a: i.set_data('drag', True)) #self._bookmark_drag_begin)
                menuitem.connect('drag-end', lambda i, *a: i.set_data('drag', False)) #self._bookmark_drag_end)
                menuitem.drag_source_set(gtk.gdk.BUTTON1_MASK, 
                        [("text/plain", 0, 0)], gtk.gdk.ACTION_COPY)
                menuitem.connect('button-release-event', 
                        self._bookmark_release, element)
            if menuitem:
                menuitem.set_label(self._bookmarks.get_title_text(element))
                label = menuitem.get_children()[0]
                label.set_max_width_chars(48)
                label.set_ellipsize(pango.ELLIPSIZE_END)
                glib.idle_add(menuitem.show_all)
                glib.idle_add(menu.add, menuitem)
                menuitem = None
        return menu

    def _get_bookmark_data(self, menuitem, context, selection, info, timestamp, bookmark):
        selection.set('text/plain', 8, self._bookmarks.get_uri(bookmark))

class FolderSelect(gtk.Window):

    def __init__(self, bookmarks, title, window_icon, buttons_tup):
        """ FolderSelect (bookmarks, title, icon, buttons_tup) ->
        buttons_tup = (ok_button_icon, response, cancel_button_icon, response)
        
        """

        assert type(buttons_tup) == tuple and len(buttons_tup) == 4, \
                "Fourth argument must be tuple pair of button and response"

        super(FolderSelect, self).__init__()

        self._bookmarks = bookmarks

        self._loop_level = 0
        self._response = None
        self._folder_created = False

        self._selected_folder = self._bookmarks.get_top_parent()
        self._active_iter = None
        self._skip_folder = None

        accels = gtk.AccelGroup()
        accels.connect_group(gtk.gdk.keyval_from_name('Escape'), 0, 
                gtk.ACCEL_VISIBLE, 
                lambda *a: \
                        self._response_button_clicked(None, 
                            gtk.RESPONSE_CANCEL))

        self.add_accel_group(accels)

        self.set_title(title)

        folder_frame = gtk.Frame()
        folder_frame.set_shadow_type(0)
        frame_label = gtk.Label('<b>Select Folder</b>')
        frame_label.set_use_markup(True)
        folder_frame.set_label_widget(frame_label)

        folder_vbox = gtk.VBox(spacing=6)

        self._tree_model = gtk.TreeStore(gtk.gdk.Pixbuf, str, object)
        self._folder_tree = gtk.TreeView(self._tree_model)

        pix_renderer = gtk.CellRendererPixbuf()
        text_renderer = gtk.CellRendererText()
        pix_col = gtk.TreeViewColumn(None, pix_renderer, pixbuf=0)
        text_col = gtk.TreeViewColumn('Folder Name', text_renderer, text=1)
        self._folder_tree.append_column(pix_col)
        self._folder_tree.append_column(text_col)

        self._folder_tree.connect('cursor-changed', self._folder_selected)

        scrollbox = gtk.ScrolledWindow()
        scrollbox.set_policy('automatic', 'automatic')
        scrollbox.set_shadow_type('in')

        scrollbox.add(self._folder_tree)

        folder_vbox.pack_start(scrollbox)

        new_folder_button = gtk.Button('_New Folder')
        new_folder_button.set_use_underline(True)
        icon = gtk.Image()
        icon.set_from_icon_name('folder-new', gtk.ICON_SIZE_BUTTON)
        new_folder_button.set_image(icon)
        new_folder_button.connect('clicked', self._new_folder_clicked)

        alignment = gtk.Alignment(1.0, 0.5, 1, 1)
        alignment.add(new_folder_button)

        #folder_hbox = gtk.HBox(True)
        #folder_hbox.pack_end(alignment, True, True)
        folder_bbox = gtk.HButtonBox()
        folder_bbox.set_layout(gtk.BUTTONBOX_END)
        folder_bbox.pack_end(alignment, True, True)

        folder_vbox.pack_end(folder_bbox, False, False)

        alignment = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment.set_padding(0, 0, 12, 0)
        alignment.add(folder_vbox)
        folder_frame.add(alignment)

        # Make and setup a frame to hold the name entry.
        self._name_frame = gtk.Frame()
        self._name_frame.set_shadow_type(0)
        frame_label = gtk.Label('<b>Name</b>')
        frame_label.set_use_markup(True)
        self._name_frame.set_label_widget(frame_label)

        name_label = gtk.Label('Name:')
        self._name_entry = gtk.Entry()
        self._name_entry.connect('activate', lambda entry: \
                self._response_button_clicked(entry, gtk.RESPONSE_OK))
        name_hbox = gtk.HBox(False, 6)
        name_hbox.pack_start(name_label, False, False)
        name_hbox.pack_start(self._name_entry, True, True)

        alignment = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment.set_padding(0, 0, 12, 0)
        alignment.add(name_hbox)
        self._name_frame.add(alignment)

        # Make a frame to hold the uri entry.
        self._uri_frame = gtk.Frame()
        self._uri_frame.set_shadow_type(0)
        frame_label = gtk.Label('<b>URI</b>')
        frame_label.set_use_markup(True)
        self._uri_frame.set_label_widget(frame_label)

        uri_label = gtk.Label('URI:')
        self._uri_entry = gtk.Entry()
        self._uri_entry.connect('activate', lambda entry: \
                self._response_button_clicked(entry, gtk.RESPONSE_OK))
        uri_hbox = gtk.HBox(False, 6)
        uri_hbox.pack_start(uri_label, False, False)
        uri_hbox.pack_start(self._uri_entry, True, True)

        alignment = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment.set_padding(0, 0, 12, 0)
        alignment.add(uri_hbox)
        self._uri_frame.add(alignment)

        # Create the Ok and Cancel buttons.
        #button_hbox = gtk.HBox(True, 6)
        button_bbox = gtk.HButtonBox()
        button_bbox.set_layout(gtk.BUTTONBOX_END)
        button_bbox.set_spacing(6)
        ok_button = gtk.Button(buttons_tup[0])
        ok_button.set_use_stock(True)
        ok_button.connect('clicked', self._response_button_clicked, 
                buttons_tup[1])
        cancel_button = gtk.Button(buttons_tup[2])
        cancel_button.set_use_stock(True)
        cancel_button.connect('clicked', self._response_button_clicked, 
                buttons_tup[3])

        button_bbox.pack_start(cancel_button, True, True)
        button_bbox.pack_end(ok_button, True, True)
        #button_hbox.pack_end(ok_button)
        #button_hbox.pack_start(cancel_button)

        button_align = gtk.Alignment(1.0, 0.5, 0, 1)
        button_align.add(button_bbox)

        vbox = gtk.VBox(spacing=6)
        vbox.pack_start(folder_frame)
        vbox.pack_start(self._name_frame, False, False)
        vbox.pack_start(self._uri_frame, False, False)
        vbox.pack_start(button_align, False, False)

        alignment = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment.set_padding(12, 12, 12, 12)
        alignment.add(vbox)

        self.add(alignment)

        self.set_default_size(400, 400)
        self.set_icon_name(window_icon)
        self.connect('destroy', self._destroyed)

        self._name_frame.set_no_show_all(True)
        self._uri_frame.set_no_show_all(True)

    def set_name(self, name):
        self._name_frame.set_no_show_all(False)
        self._name_frame.show_all()
        self._name_entry.set_text(name)

    def set_uri(self, uri):
        self._uri_frame.set_no_show_all(False)
        self._uri_frame.show_all()
        self._uri_entry.set_text(uri)

    def set_folder(self, folder):
        self._selected_folder = folder

    def skip_folder(self, folder):
        self._skip_folder = folder

    def get_name(self):
        return self._name_entry.get_text()

    def get_uri(self):
        return self._uri_entry.get_text()

    def get_folder(self):
        return self._selected_folder

    def get_folder_created(self):
        return self._folder_created

    def run(self):
        self._setup_folder_view()
        self.show_all()

        self._name_entry.grab_focus()

        # Select the current folder.
        if self._active_iter:
            self._folder_tree.get_selection().select_iter(self._active_iter)
            self._folder_tree.set_cursor(self._tree_model.get_path(self._active_iter))

        self._loop_level = gtk.main_level() + 1
        gtk.main()
        return self._response

    def _setup_folder_view(self):
        icon_theme = gtk.icon_theme_get_default()
        icon = icon_theme.load_icon('gtk-directory', 16, 
                gtk.ICON_LOOKUP_USE_BUILTIN)

        self._tree_model.clear()

        iter = self._tree_model.append(None, (icon, 'Bookmarks', 
            self._bookmarks.get_top_parent()))
        self._build_folder(iter, self._bookmarks.get_top_parent(), icon)
        self._folder_tree.expand_all()

    def _build_folder(self, parent_iter, parent, icon):
        for element in self._bookmarks.get_folder_list_sorted(parent): 
            if element != self._skip_folder:
                name = self._bookmarks.get_title_text(element)
                iter = self._tree_model.append(parent_iter, 
                        (icon, name, element))
                if element == self._selected_folder:
                    self._active_iter = iter
                self._build_folder(iter, element, icon)

    def _folder_selected(self, folder_tree):
        row, col = folder_tree.get_cursor()
        if row and col:
            model = folder_tree.get_model()
            self._selected_folder =  model.get_value(model.get_iter(row), 2)

    def _destroyed(self, *args):
        self._response = gtk.RESPONSE_CANCEL
        if gtk.main_level() == self._loop_level:
            gtk.main_quit()

    def _response_button_clicked(self, response_button, response):
        self._response = response
        if gtk.main_level() == self._loop_level:
            gtk.main_quit()

    def _new_folder_clicked(self, new_folder_button):
        result_tup = NameEntry.name_entry('Enter Folder Name', 'folder-new', 
                'New Folder')
        if result_tup:
            name, emtpy = result_tup
            new_folder = self._bookmarks.add_folder(name, 
                    self._selected_folder)
            self._folder_created = True
            self._setup_folder_view()
        else:
            self._folder_created = False

    @classmethod
    def folder_select(cls, window_title, icon, bookmarks, name, parent=None, 
            uri=None, skip=None):
        """ folder_select(window_title, icon, bookmarks, parent=None, 
        name=None, uri=None, skip=None) ->
        Show a folder select and return the result.

        """

        select_folder = FolderSelect(bookmarks, window_title, icon,
                buttons_tup=(gtk.STOCK_OK, gtk.RESPONSE_OK, gtk.STOCK_CANCEL, 
                    gtk.RESPONSE_CANCEL))
        if skip:
            select_folder.skip_folder(skip)

        if parent:
            select_folder.set_folder(parent)

        if uri:
            select_folder.set_uri(uri)

        select_folder.set_name(name)
        response = select_folder.run()

        dest_folder = select_folder.get_folder()
        new_name = select_folder.get_name()
        new_uri = select_folder.get_uri()
        folder_created = select_folder.get_folder_created()
        select_folder.destroy()

        return {'response': response, 'dest_folder': dest_folder, 
                'name': new_name, 'uri': new_uri, 
                'folder_created': folder_created}

class NameEntry(gtk.Window):

    def __init__(self, title='Enter Name', default_text=None, 
            window_icon='gtk-edit', buttons_tup=None):

        assert type(buttons_tup) == tuple and len(buttons_tup) == 4, \
                "Fourth argument must be tuple pair of button and response"

        super(NameEntry, self).__init__()

        accels = gtk.AccelGroup()
        accels.connect_group(gtk.gdk.keyval_from_name('Escape'), 0, 
                gtk.ACCEL_VISIBLE,  
                lambda *a: self._response_button_clicked(None, 
                    gtk.RESPONSE_CANCEL))

        self._loop_level = 0
        self._response = None

        self.add_accel_group(accels)

        self.set_title(title)

        vbox = gtk.VBox(spacing=6)

        frame = gtk.Frame()
        frame.set_shadow_type(0)
        frame_label = gtk.Label('<b>%s:</b>' % title)
        frame_label.set_use_markup(True)
        frame.set_label_widget(frame_label)
        
        name_label = gtk.Label('_Name:')
        name_label.set_use_underline(True)
        self._name_entry = gtk.Entry()
        self._name_entry.set_text(default_text)
        self._name_entry.connect('activate', lambda entry: \
                self._response_button_clicked(entry, gtk.RESPONSE_OK))

        hbox = gtk.HBox(False, 6)
        hbox.pack_start(name_label, False, False)
        hbox.pack_start(self._name_entry, True, True)

        alignment = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment.set_padding(0, 0, 12, 0)
        alignment.add(hbox)
        frame.add(alignment)

        vbox.pack_start(frame, False, False)

        self._uri_frame = gtk.Frame()
        self._uri_frame.set_shadow_type(0)
        frame_label = gtk.Label('<b>Edit Uri:</b>')
        frame_label.set_use_markup(True)
        self._uri_frame.set_label_widget(frame_label)
        
        uri_label = gtk.Label('_Uri:')
        uri_label.set_use_underline(True)
        self._uri_entry = gtk.Entry()
        self._uri_entry.connect('activate', lambda entry: \
                self._response_button_clicked(entry, gtk.RESPONSE_OK))

        hbox = gtk.HBox(False, 6)
        hbox.pack_start(uri_label, False, False)
        hbox.pack_start(self._uri_entry, True, True)

        alignment = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment.set_padding(0, 0, 12, 0)
        alignment.add(hbox)
        self._uri_frame.add(alignment)

        vbox.pack_start(self._uri_frame, False, False)

        self.set_size_request(250, 115)

        hbox = gtk.HBox(True, 6)

        cancel_button = gtk.Button(buttons_tup[2])
        cancel_button.set_use_stock(True)
        cancel_button.connect('clicked', self._response_button_clicked, 
                buttons_tup[3])

        ok_button = gtk.Button(buttons_tup[0])
        ok_button.set_use_stock(True)
        ok_button.connect('clicked', self._response_button_clicked, 
                buttons_tup[1])

        hbox.pack_start(cancel_button, True, True)
        hbox.pack_start(ok_button, True, True)

        alignment = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment.set_padding(6, 0, 0, 0)
        alignment.add(hbox)

        vbox.pack_start(alignment, False, False)

        alignment = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment.set_padding(12, 12, 12, 12)
        
        alignment.add(vbox)

        self.add(alignment)

        self.set_position(gtk.WIN_POS_MOUSE)
        self.set_modal(True)
        self.set_resizable(False)
        self.set_icon_name(window_icon)
        self.connect('destroy', self._destroyed)
        self.grab_focus()
        self._name_entry.grab_focus()

    def run(self):
        self.show_all()
        self._loop_level = gtk.main_level() + 1
        gtk.main()
        return self._response

    def _destroyed(self, *args):
        self._response = gtk.RESPONSE_CANCEL
        if gtk.main_level() == self._loop_level:
            gtk.main_quit()

    def _response_button_clicked(self, response_button, response):
        self._response = response
        if gtk.main_level() == self._loop_level:
            gtk.main_quit()

    def set_edit_uri(self, value, uri=None):
        if value:
            self._uri_frame.set_no_show_all(False)
            self._uri_frame.show_all()
            self._uri_entry.set_text(uri)
            self.set_size_request(250, 167)
        else:
            self._uri_frame.set_no_show_all(True)
            self._uri_frame.hide_all()
            self.set_size_request(250, 115)
    
    def get_uri(self):
        return self._uri_entry.get_text()

    def get_name(self):
        return self._name_entry.get_text()

    @classmethod
    def name_entry(cls, window_title, icon, title, uri=None):
        """ name_entry(window_title, icon, title=None, uri=None) -> Crate a 
        NameEntry and return the result.

        """

        new_bookmark_entry = NameEntry(window_title, title, icon, 
                buttons_tup=(gtk.STOCK_OK, gtk.RESPONSE_OK, 
                    gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
        if uri:
            new_bookmark_entry.set_edit_uri(True, uri)
        else:
            new_bookmark_entry.set_edit_uri(False)

        response = new_bookmark_entry.run()
        title = new_bookmark_entry.get_name()
        uri = new_bookmark_entry.get_uri()
        new_bookmark_entry.destroy()
        if response == gtk.RESPONSE_OK:
            return (title, uri)
        else:
            return ()

