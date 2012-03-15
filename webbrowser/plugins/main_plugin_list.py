# This file is part of browser.  This is plugin to load and unload plugins.
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

""" Plugin list to load an unload other plugins.

"""

import os

import gtk
import gobject
import glib

class PluginList(gtk.ScrolledWindow):
    """ PluginList -> A list of plugins.

    """

    __gsignals__ = {
            'enable-plugin' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)),
            'reload-plugin' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_PYOBJECT,)),
            'refresh' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                ()),
            }

    def __init__(self):
        """ TabList -> A list view for holding the history of the tabs that 
        were closed.

        """

        super(PluginList, self).__init__()

        # Set the title that TabBase class will display on the tab this 
        # object will be added to.
        self._title = "Plugins"

        # Set the icon that TabBase class will display on the tab this 
        # object will be added to.
        self._icon = gtk.Image()
        self.set_icon('applications-utilities')

        # The current folder is used by the open and save dialogs.
        self._current_folder = os.getenv('HOME')

        # Setup the scrolled window.
        # Set the shadow to be in and the policy for displaying the scroll 
        # bars to automatic.
        self.set_policy('automatic', 'automatic')
        self.set_shadow_type(gtk.SHADOW_IN)

        # A tuple defining the columns and thier attributes.
        # Format:
        # (Name, Renderer, value_dict, resizable, data_type)
        column_tup = (
                ('', gtk.CellRendererToggle(), {'active':0}, False, 
                    bool, ('toggled', self._plugin_toggled)),
                ('Title', gtk.CellRendererText(), {'text':1}, True, str, ()),
                ('Description', gtk.CellRendererText(), {'text':2}, True, 
                    str, ()),
                )

        # Create a treeview and make set it to allow multiple selections
        # and rubber band selections.
        self._list_view = gtk.TreeView()
        self._list_view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self._list_view.set_rubber_banding(True)

        col_types = []

        # Build the columns for the treeview.
        for (title, renderer, value, resizable, col_type, extra) in column_tup:
            if extra:
                renderer.connect(*extra)
            column = gtk.TreeViewColumn(title, renderer, **value)
            column.set_resizable(resizable)
            self._list_view.append_column(column)

            # Collect the data types for each column.
            col_types.append(col_type)

        # Add some extra non-visible column data types.  These columns are
        # used to hold the pid, tab_index, history_index, and history_list 
        # of each tab.
        col_types.extend((object,))

        # Create the liststore using the data types in col_types list.
        self._list_store = gtk.ListStore(*col_types)
        self._list_view.set_model(self._list_store)

        self._list_view.connect('button-release-event', 
                self._view_button_released)
        self._list_view.connect('key-press-event', self._view_key_pressed)

        # The pop-up menu. 
        self._menu = self._build_menu()

        self.add(self._list_view)
        self.show_all()

    def _build_menu(self):
        """ _build_menu() -> Build the pop-up menu.

        """

        menu = gtk.Menu()

        # A tuple to hold the information used to make each menu item.
        # Format:
        # (item_name, (icon_name, label_text, enabled, accel, callback))
        item_tup = (
                #gtk.SeparatorMenuItem(),
                ('_reload_item', ('gtk-refresh', '_Reload Selected', False, 
                    None, self._reload_button_released)),
                ('_refresh_item', ('gtk-refresh', 'Re_fresh List', True, None, 
                    self._refresh_button_released)),
                #('_remove_tab_item', ('list-remove', 'Remove _Selected', 
                    #False, 'Delete', self._remove_tab_button_released)),
                )

        accel_group = gtk.AccelGroup()
        menu.set_accel_group(accel_group)

        # Build the menu.
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

    def _view_button_released(self, list_view, event):
        """ _view_button_released -> Called when the mouse button is released
        on the tab list. 
        
        """

        # Get the item that is under the mouse
        path = list_view.get_path_at_pos(int(event.x), int(event.y))
        selection = list_view.get_selection()
        if path:
            # Select the item under the mouse if one or fewer items are 
            # selected.
            if selection.count_selected_rows() <= 1 and event.button == 3 \
                    or event.button == 2:
                selection.unselect_all()
                selection.select_path(path[0])

            self._reload_item.set_sensitive(True)
        else:
            selection.unselect_all()

            self._reload_item.set_sensitive(False)
            
        if event.button == 3:
            # Pop up menu
            self._menu.popup(None, None, None, event.button, event.time, None)

            return True
        elif event.button == 2:
            # Remove the item under the mouse from the list when the 
            # middle mouse button is clicked
            #self._remove_selected()

            return True

        return False

    def _view_key_pressed(self, list_view, event):
        """ _view_key_pressed -> Called when a key is pressed on the tab list.
        
        """

        #if event.keyval == gtk.gdk.keyval_from_name('Delete'):
            #self._remove_selected()
            #return True

        return False

    def _plugin_toggled(self, renderer, path):
        """ _plugin_toggled -> Toggle a plugin.

        """

        self._list_store[path][0] = not self._list_store[path][0]
        self.emit('enable-plugin', self._list_store[path][1], 
                self._list_store[path][0])

    def _refresh_button_released(self, refresh_item, event):
        """ _refresh_button_released -> Refresh the list of plugins.

        """

        self.emit('refresh')

    def _reload_button_released(self, reload_item, event):
        """ _reload_button_released -> Reload the selected items.

        """

        reload_item.parent.popdown()

        selection = self._list_view.get_selection()

        glib.idle_add(self._reload_list, selection.get_selected_rows()[1])

    def _reload_list(self, plugin_list):
        """ _reload_list(plugin_list) -> Reload all the plugins in 
        'plugin_list.'

        """
        
        name_list = []
        name = None
        for row in plugin_list:
            if type(row) == tuple:
                iter = self._list_store.get_iter(row)
            else:
                iter = row.iter
            name_list.append(self._get_name(iter))

        if __name__ in name_list:
            index = name_list.index(__name__)
            name = name_list.pop(index)

            
        self.emit('reload-plugin', name_list)
        if name:
            self.emit('reload-plugin', [name,])

    def _get_name(self, iter):
        """ _get_name(iter) -> Return the name of the plugin at iter.

        """

        return self._list_store.get_value(iter, 1)

    def _remove_item(self, iter):
        """ _remove_item -> Remove the item pointed to by iter.

        """

        self._list_store.remove(iter)

    def _remove_selected(self):
        """ _remove_selected -> Remove all the selected tabs.

        """

        selection = self._list_view.get_selection()

        row_list = selection.get_selected_rows()[1]
        row_list.reverse()
        for row in row_list:
            iter = self._list_store.get_iter(row)
            self._remove_item(iter)

    def remove_plugin(self, name):
        """ remove_plugin(name) -> Remove the named plugin from the list.

        """

        for row in self._list_store:
            iter = row.iter
            if self._list_store.get_value(iter, 1) == name:
                self._remove_item(iter)

    def add_plugin(self, loaded, name, desc):
        """ add_plugin(loaded, name, desc) -> Add a plugin to the list with its
        description.

        """

        # Add plugins when the glib main loop is ready to, so the interface
        # doesn't freeze.
        glib.idle_add(self._add_plugin, loaded, name, desc, None)

    def _add_plugin(self, loaded, name, desc, obj):
        """ _add_plugin(loaded, name, desc, obj) -> Add a plugin to the list 
        with its description.

        """

        # Check if the plugin is already in the list and update its values
        # if it is.
        for row in self._list_store:
            iter = row.iter
            if self._list_store.get_value(iter, 1) == name:
                # The plugin was already in the list so update its state.
                self._list_store.set_value(iter, 0, loaded)
                self._list_store.set_value(iter, 2, desc)
                return 

        # Add any plugin that was not already listed.
        self._list_store.append((loaded, name, desc, obj))

    def set_icon(self, icon_name):
        """ set_icon(icon_name) -> Set the icon from icon_name.

        """

        self._icon.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)

    def get_icon(self):
        """ get_icon() -> Return the icon.

        """

        return self._icon


    def get_title(self):
        """ get_title -> Return the title.

        """

        return self._title

    def close(self):
        """ close -> Return False otherwise TabBase will close it.

        """

        return False

class PluginManager(object):
    """ A plugin list that allows the user to enable and disable plugins, and
    refresh the plugin list.

    """

    def __init__(self, browser):
        """ PluginManager(browser) -> Enable or disable plugins.

        """

        self._browser = browser
        self._plugin_list = None

    def run(self):
        """ run -> Setup the plugin list.

        """

        self._plugin_list = PluginList()

        # Connect to the plugin loaders signals.
        self._browser._plugins.connect('plugin-changed', self._add_plugin)
        self._browser._plugins.connect('plugin-removed', self._remove_plugin)

        # Add the already loaded plugins.
        for name, module_dict in self._browser._plugins.get_list().iteritems():
            self._add_to_list(name, module_dict)

        # Connect to the plugin list signals.
        plugin_connect_dict = {
                'enable-plugin':(self._toggle_plugin,),
                'reload-plugin':(self._reload_plugin,),
                'refresh':(self._refresh,),
                }
        for signal, handler_tup in plugin_connect_dict.iteritems():
            self._plugin_list.connect(signal, *handler_tup)

        self._browser._term_book.new_tab(self._plugin_list, True)

    def exit(self):
        """ exit -> Disconnect from the plugin loaders signals and remove the
        plugin list from the bottom panel.

        """

        try:
            self._browser._plugins.disconnect_by_func(self._add_plugin)
            self._browser._plugins.disconnect_by_func(self._remove_plugin)
        except Exception as err:
            print(err)
        finally:
            # No matter what remove the plugin list from the panel.
            glib.idle_add(self._browser._term_book.close_tab, 
                    self._plugin_list, True)
            self._plugin_list = None

    def _add_plugin(self, plugins, name, module_dict):
        """ _add_plugin -> Add the named plugin to the list.

        """

        self._add_to_list(name, module_dict)

    def _remove_plugin(self, plugins, name):
        """ _remove_plugin -> Remove the named plugin from the list.

        """

        self._plugin_list.remove_plugin(name)

    def _add_to_list(self, name, module_dict):
        """ _add_to_list(name, module_dict) -> Add the named plugin to the
        plugin list if 'module_dict' is not empty.

        """

        if module_dict:
            if name == __name__:
                # We already know that this plugin is loaded.
                loaded = True
            else:
                # If the 'plugin' key is not None then that means the plugin is
                # loaded.
                loaded = module_dict['plugin'] != None

            # Get a cleaned up module description.
            desc = ' '.join(str(module_dict['module'].__doc__).split('\n')).strip()

            self._plugin_list.add_plugin(loaded, name, desc)

    def _toggle_plugin(self, plugin_list, name, enable):
        """ _toggle_plugin -> Enable or disable the named plugin.

        """

        try:
            if enable:
                self._browser._plugins.enable(name)
            else:
                self._browser._plugins.disable(name)
        except Exception as err:
            print("Error: %s" % err)

    def _reload_plugin(self, plugin_list, name_list):
        """ _reload_plugin -> Tell the plugin loader to reload all the
        plugins in 'name_list.'

        """

        for plugin_name in name_list:
            self._browser._plugins.reload(plugin_name)

    def _refresh(self, plugin_list):
        """ _refresh -> Tell the plugin loader to refresh the list of 
        available plugins, loading new ones and unloading not available ones.

        """

        self._browser._plugins.refresh()

Plugin = PluginManager
