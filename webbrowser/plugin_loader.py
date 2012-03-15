# This file is part of browser, and the plugin loader.
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

""" A plugin loader object.

Plugins should be passed the object to expose to the plugins.  When loading
a plugin it should be given the path and a prefix to differentiate between
plugins for the browser and plugins for each tab.

"""

import os
import sys
import glob
import json

import gobject
import glib

from defaults import APP_NAME

class Plugins(gobject.GObject):
    """ Plugins -> Handles the loading and running of plugins.

    """

    __gsignals__ = {
            'plugin-changed' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, (gobject.TYPE_STRING, 
                    gobject.TYPE_PYOBJECT)),
            'plugin-removed' : (gobject.SIGNAL_RUN_LAST, 
                gobject.TYPE_PYOBJECT, (gobject.TYPE_STRING,)),
            }

    def __init__(self, exposed_object, profile='default', use_config=True):
        """ Plugins(exposed_object, profile='default', use_config=True) -> 
        Initialize the plugin class.

        """

        super(Plugins, self).__init__()

        self._exposed_object = exposed_object
        self._use_config = use_config

        self._profile = profile

        self._plugin_dict = {}
        self._config_path = '%s/%s/%s' % \
                (glib.get_user_config_dir(), APP_NAME, profile)
        self._plugin_path = '%s/%s/plugins' % \
                (glib.get_user_config_dir(), APP_NAME)

        # Create user plugin directory if it does not exist.
        if not os.path.isdir(self._plugin_path):
            os.mkdir(self._plugin_path)

        self._config_filename = None
        self._path = [self._plugin_path]
        self._prefix = None
        self._config_dict = {}

    def refresh(self):
        """ refresh() -> Refresh the list of plugins.

        """

        self.load_list(self._path, self._prefix)

    def load_list(self, path, prefix):
        """ build_list(path, prefix) -> Load a list of plugins in path that
        that start with prefix.

        """

        if not isinstance(path, list):
            if not os.path.isdir(path):
                return False

        self._path.append(path)
        self._prefix = prefix
        self._config_filename = '%s/%s_plugins.conf' % (self._config_path, prefix)

        # Load the plugin config.
        self._load_config()

        plug_name_list = list(self._plugin_dict.keys())

        for path in self._path:
            if path not in sys.path:
                sys.path.append(path)
            for filename in glob.iglob('%s/%s_*.py' % (path, prefix)):
                # Skip anything except files.
                if not os.path.isfile(filename):
                    continue

                # The plugin name is the filename without the extension.
                plugin_name = filename.split('/')[-1][:-3]
                if plugin_name not in self._plugin_dict:
                    self._plugin_dict[plugin_name] = {
                            'module':None,
                            'plugin':None
                            }
                    self._load(plugin_name)
                else:
                    # Keep track of which plugins still exist.
                    if plugin_name in plug_name_list:
                        plug_name_list.remove(plugin_name)

        # Remove any plugins that no longer exist.
        for plugin_name in plug_name_list:
            glib.idle_add(self.remove, plugin_name)

    def _load_config(self):
        """ _load_config -> Load the plugin config from the config file.

        """

        if not self._use_config:
            return

        try:
            with open(self._config_filename, 'r') as config_file:
                conf_dict = json.loads(config_file.read())
                self._config_dict = conf_dict
        except Exception as err: #IOError as err:
            # Create the plugin directory and config file if it does not
            # exist.
            print("Error loading plugin config: %s" % err)
            print("Creating empty plugin config.")
            open(self._config_filename, 'w').close()

    def _save_config(self):
        """ _save_config -> Save the plugin enable status to the config file.

        """

        if not self._use_config or not self._config_dict:
            return

        try:
            with open(self._config_filename, 'w') as config_file:
                conf_str = json.dumps(self._config_dict, indent=4)
                config_file.write(conf_str)
        except Exception as err:
            print("Error saving plugin config: %s" % err)

    def _update_config(self, save=True):
        """ _update_config(save=True) -> Update the classes config 
        dictionary to contain the status of the loaded plugins.

        """

        if not self._use_config:
            return

        # Loop through all the loaded plugins.
        for plugin_name in self._plugin_dict.iterkeys():
            if self.is_loaded(plugin_name):
                self._config_dict[plugin_name] = self.is_enabled(plugin_name)
            else:
                self._config_dict.pop(plugin_name, None)

        if save:
            self._save_config()

    def remove(self, plugin_name):
        """ remove(plugin_name) -> Disable and remove the named plugin.

        """

        # Disable the plugin before removing it.
        self._disable(plugin_name)
        self._plugin_dict.pop(plugin_name, None)
        # Remove the plugins config entry.
        self._config_dict.pop(plugin_name, None)
        self.emit('plugin-removed', plugin_name)

    def unload(self):
        """ unload -> Unload all plugins.

        """

        self._update_config()

        for plugin_name in self._plugin_dict.iterkeys():
            self.disable(plugin_name, update_config=False)

    def is_enabled(self, plugin_name):
        """ is_enabled(plugin_name) -> Returns a boolean value indecating
        whether the named plugin is enabled.

        """

        module_dict = self._plugin_dict.get(plugin_name, {})
        return (module_dict.get('plugin', None) != None)

    def is_loaded(self, plugin_name):
        """ is_loaded(plugin_name) -> Returns a boolean value indecating
        whether the plugin is loaded.

        """

        module_dict = self._plugin_dict.get(plugin_name, {})
        return (module_dict.get('module', None) != None)

    def get_plugin(self, plugin_name):
        """ get_plugin(plugin_name) -> Returns the plugin object if it is
        enabled, otherwise None.

        """

        module_dict = self._plugin_dict.get(plugin_name, {})
        return module_dict.get('plugin', None)

    def enable(self, plugin_name, update_config=True):
        """ enable(plugin_name, update_config=True) -> Enable 'plugin_name.'

        """

        glib.idle_add(self._enable, plugin_name, update_config)

    def _enable(self, plugin_name, update_config=True):
        """ _enable(plugin_name, update_config=True) -> Enable 'plugin_name.'

        """

        module_dict = self._plugin_dict.get(plugin_name, {})
        module = module_dict.get('module', None)
        plugin = module_dict.get('plugin', None)

        if module and not plugin:
            if hasattr(module, 'Plugin'):
                plugin = module.Plugin(self._exposed_object)
                try:
                    plugin.run()
                except Exception as err:
                    print(err)
                    plugin.exit()
                    plugin = None

                module_dict['plugin'] = plugin
                self._plugin_dict[plugin_name].update(module_dict)

        self.emit('plugin-changed', plugin_name, 
                self._plugin_dict[plugin_name])

        if update_config:
            self._update_config()

    def disable(self, plugin_name, update_config=True):
        """ disable(plugin_name, update_config=True) -> Disable the named 
        plugin.

        """

        glib.idle_add(self._disable, plugin_name, update_config)

    def _disable(self, plugin_name, update_config=True):
        """ _disable(plugin_name, update_config=True) -> Disable the named 
        plugin.

        """

        module_dict = self._plugin_dict.get(plugin_name, {})
        module = module_dict.get('module', None)
        plugin = module_dict.get('plugin', None)

        if module:
            if plugin:
                plugin.exit()
                module_dict['plugin'] = None
                self._plugin_dict[plugin_name].update(module_dict)

        self.emit('plugin-changed', plugin_name, 
                self._plugin_dict[plugin_name])

        if update_config:
            self._update_config()

    def reload(self, plugin_name=None):
        """ reload(plugin_name=None) -> Reload the plugin 'plugin_name.' If
        'plugin_name' is not set then reload all the plugins.

        """

        if not plugin_name:
            for name in self._plugin_dict.iterkeys():
                self._disable(name, update_config=False)
                self._load(name)
        else:
            self._disable(plugin_name, update_config=False)
            self._load(plugin_name)

    def get_list(self):
        """ get_list -> Return a dictionary of plugin names linked to their
        respective plugin objects.

        """

        return self._plugin_dict

    def get_iter(self):
        """ get_iter -> A generator function that generates a two-tuple
        of plugin name and whether or not it is enabled.

        """

        for plugin_name, mod_dict in self._plugin_dict.iteritems():
            yield (plugin_name, (mod_dict.get('plugin', None) != None))

    def _module(self, plugin_name):
        """ _module(plugin_name) -> Return the module belonging to plugin_name
        or None.

        """

        module_dict = self._plugin_dict.get(plugin_name, {})
        return module_dict.get('module', None)

    def _load(self, plugin_name):
        """ _load(plugin_name) -> Load the plugin 'plugin_name.'

        """

        module = self._module(plugin_name)
        if module:
            cmd_str = 'reload(module)'
        else:
            cmd_str = '__import__("%s")' % plugin_name

        try:
            module = eval(cmd_str)
            module.profile = self._profile
        except Exception as err:
            print(err)
            module = None

        if hasattr(module, 'Plugin'):
            self._plugin_dict[plugin_name].update({'module':module})
            self.emit('plugin-changed', plugin_name, 
                    self._plugin_dict[plugin_name])

            if module:
                if vars(module).get('AUTO_LOAD', True) and self._config_dict.get(plugin_name, True):
                    self.enable(plugin_name, update_config=False)
        else:
            # Remove plugins that have no 'Plugin' class.
            self._plugin_dict.pop(plugin_name)

        self._update_config(save=False)

class PluginBase(object):
    """ A generic plugin class for plugins to inherit so they have the
    default plugin settings.

    """

    def __init__(self, browser):
        """ Plugin

        """

        self._browser = browser

    def run(self):
        pass

    def exit(self):
        pass
