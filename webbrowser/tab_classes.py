# This file is part of browser, and contains the classes related to tabs.
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

""" Tab book classes.

"""

import os
import json
import threading

import gtk
import glib
import gobject
import pango
import vte

from classes import OpenDialog, SaveDialog

class TermBox(gtk.HBox):

    __gsignals__ = {
            'hide-term' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.GObject,)),
            'title-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING,))
            }

    def __init__(self, directory, command=None, argv=[], enable_input=False):
        super(TermBox, self).__init__()

        terminal = vte.Terminal()

        terminal.set_audible_bell(False)
        terminal.set_visible_bell(False)
        terminal.set_mouse_autohide(True)

        self._pid = terminal.fork_command(command=command, argv=argv, 
                directory=directory)

        #fontname = 'Terminus 10'
        fontname = ''
        scrollback_lines = 10240
        backcolor = gtk.gdk.Color('#fff')
        forecolor = gtk.gdk.Color('#000')
        palette = [gtk.gdk.Color('#2e3436'), gtk.gdk.Color('#c00'), 
                   gtk.gdk.Color('#4e9a06'), gtk.gdk.Color('#c4a000'), 
                   gtk.gdk.Color('#3465a4'), gtk.gdk.Color('#75507b'), 
                   gtk.gdk.Color('#060698209a9a'), 
                   gtk.gdk.Color('#d3d7cf'), gtk.gdk.Color('#555753'), 
                   gtk.gdk.Color('#ef2929'), gtk.gdk.Color('#8ae234'), 
                   gtk.gdk.Color('#fce94f'), gtk.gdk.Color('#729fcf'), 
                   gtk.gdk.Color('#ad7fa8'), gtk.gdk.Color('#34e2e2'), 
                   gtk.gdk.Color('#eeeeec')]

        terminal.set_colors(forecolor, backcolor, palette)
        terminal.set_font_from_string(fontname)
        terminal.set_scrollback_lines(scrollback_lines)

        terminal.connect('button-press-event', self._term_click_callback, 
                enable_input)
        terminal.connect('key-press-event', self._term_key_press_callback, 
                enable_input)
        terminal.connect('window-title-changed', self._term_title_changed)
        terminal.connect('child-exited', lambda term, command, argv, 
                directory: term.fork_command(command=command, argv=argv, 
                    directory=directory), command, argv, directory)

        scroll_bar = gtk.VScrollbar(terminal.get_adjustment())
        scroll_bar.show()

        self.pack_start(terminal)
        self.pack_start(scroll_bar, False)
        self.show_all()

        self._menu = gtk.Menu()
        self._build_menu(enable_input)

    def _build_menu(self, enable_input):
        self._copy_menuitem = gtk.ImageMenuItem(gtk.STOCK_COPY) 
        self._menu.append(self._copy_menuitem)

        if enable_input:
            self._paste_menuitem = gtk.ImageMenuItem(gtk.STOCK_PASTE) 
            self._menu.append(self._paste_menuitem)

        self._menu.append(gtk.SeparatorMenuItem())
        
        icon = gtk.Image()
        icon.set_from_icon_name('stock_slide-showhide', gtk.ICON_SIZE_MENU)
        self._hide_menuitem = gtk.ImageMenuItem('Hide') 
        self._hide_menuitem.set_image(icon)
        self._hide_menuitem.connect('activate', self._hide_term)

        self._menu.append(self._hide_menuitem)
        self._menu.show_all()

    def get_title(self):
        return self.get_children()[0].get_window_title()

    def get_pid(self):
        return self._pid

    def _term_key_press_callback(self, term, event, enable_input):
        return not enable_input

    def _term_click_callback(self, term, event, enable_input):
        if event.button == 3:
            if enable_input:
                clipboard = term.get_clipboard('CLIPBOARD')
                clipboard.request_text(lambda clipboard, text, data: \
                        self._paste_menuitem.set_sensitive((text != None)))
                self._paste_menuitem.connect('activate', self._paste_text, 
                        term)
            self._copy_menuitem.set_sensitive(term.get_has_selection())
            self._copy_menuitem.connect('activate', self._copy_text, term)
            self._menu.popup(None, None, None, event.button, event.time, None)
        elif event.button == 2:
            if not enable_input:
                return True

    def _term_title_changed(self, term):
        self.emit('title-changed', term.get_window_title())

    def _copy_text(self, copy_menuitem, terminal):
        terminal.copy_clipboard()

    def _paste_text(self, paste_menuitem, terminal):
        terminal.paste_clipboard()

    def _hide_term(self, hide_menuitem):
        self.emit('hide-term', hide_menuitem)

    def close(self):
        return False

class TabBase(gtk.Notebook):
    """ TabBase is a generic gtk Notebook object.  If present the return value
    of the widgets get_title and get_icon methods will be used to set the title
    and icon of the tab.  Also if present the widgets close method will 
    determine if the tab should be closed or not unless it is forced to close.
    
    """

    __gproperties__ = {
            'current-page' : (gobject.TYPE_PYOBJECT, 'current page', 
                'the currently active page', gobject.PARAM_READWRITE),
            }

    __gsignals__ = {
            'title-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_STRING,)),
            'exit' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
            'tab-closed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_PYOBJECT,)),
            'tab-added' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_PYOBJECT,)),
            'new-tab' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT)), 
            }

    def __init__(self, show_tabs=True, action_widget=None):
        """ TabBase(show_tabs=True) -> Initialize the tab settings for the
        notebook.  If 'show_tabs' is True the show the tabs otherwise hide
        them.

        """

        super(TabBase, self).__init__()

        self._current_tab = None
        self._previous_tab = []
        self._switch_new_tab = False
        self._toggle_tabs = not show_tabs

        connection_dict = {
                'page-added': self._page_added_callback,
                'page-removed': self._page_removed_callback,
                'switch-page': self._page_switched_callback,
                'button-press-event': self._tabbar_button_press,
                'button-release-event': self._tabbar_button_release,
                }
        for signal, callback in connection_dict.iteritems():
            self.connect(signal, callback)

        self.set_scrollable(True)
        self.set_show_tabs(show_tabs)
        if action_widget:
            self.set_action_widget(action_widget, gtk.PACK_END)

    def do_get_property(self, prop):
        """ do_get_property(prop) -> Returns the value of custom properties.

        """

        if prop.name == 'current-page':
            return self._current_tab

    def do_set_property(self, prop, value):
        """ do_set_property(prop, value) -> Set the value of properties.

        """

        if prop.name == 'current-page':
            self._current_tab = value

    def toggle_minimize_tab(self, tab=None):
        """ toggle_minimize_tab(tab=None) -> Toggle the visibility of the
        icon of 'tab' or the current tab if 'tab' is None.

        """

        if not tab:
            tab = self._current_tab
        eventbox = self.get_tab_label(tab)
        label = eventbox.get_children()[0].get_children()[-1]
        label.set_property('visible', not label.get_property('visible'))

    def toggle_hide_tab(self, tab=None):
        """ tobble_hide_tab(tab=None) -> Toggle the visibility of the title
        and icon of 'tab,' or the current tab if 'tab' is None.

        """

        if not tab:
            tab = self._current_tab
        eventbox = self.get_tab_label(tab)
        hbox = eventbox.get_children()[0]
        hbox.set_property('visible', not hbox.get_property('visible'))

    def toggle_visible(self, child=None, visible=None):
        """ toggle_visible(child=None, visible=None) -> Toggles the visibility
        of the tab window.  If child is specified it switches to that child
        before showing or instead of hiding (if child is not already focused).
        If visible is not None it us used to override the toggle and force 
        visibility either on or off.

        """

        if not child:
            child = self._current_tab

        if self._current_tab != child:
            self.set_current_page(self.get_children().index(child))
            if visible is None:
                visible = True
        else:
            if visible is None:
                visible = not self.get_property('visible')
        self.set_property('visible', visible)

    def get_current_child(self):
        """ get_current_child -> Return the child of the active tab.

        """

        return self.get_nth_page(self.get_current_page())

    def close_tab(self, child=None, force=False):
        """ close_tab(child=None, force=False) -> Close the tab that 
        contains 'child' or the current tab if child is None.  If force is
        True then remove the tab even if the child does not close.

        """

        if not child:
            child = self._current_tab

        if child not in self.get_children():
            return

        # De-select everything.
        self._grab_clipboard()

        if hasattr(child, 'close') and not force:
            if child.close():
                glib.idle_add(self._close_cleanup, child)
        else:
            glib.idle_add(self._close_cleanup, child)

    def _close_cleanup(self, child):
        """ _close_cleanup(child) -> Do some cleanup before removing and
        destroying 'child.'

        """

        # If the current tab was closed and there were previous tabs, then
        # switch to the last viewed tab in the list.
        if self._current_tab == child and self._previous_tab:
            self.set_current_page(self.page_num(self._previous_tab.pop()))

        # Tell anybody listening that this tab was closed.
        self.emit('tab-closed', child)

        # Remove the tab.
        if child in self.get_children():
            self.remove_page(self.page_num(child))

        # Finally destroy the child of the tab.
        #child.destroy()
        #print('child destroyed')

    def _grab_clipboard(self):
        """ _grab_clipboard() -> Grab the clipboard so the webview can be
        destroyed without causing a segfault.

        """

        # Grab ownership of the clipboard so webkit doesn't segfault.
        clipboard = gtk.clipboard_get('PRIMARY')
        selected_text = clipboard.wait_for_text()
        if selected_text:
            clipboard.set_text(selected_text)
            clipboard.store()

    def new_tab(self, child, switch_to=False):
        """ new_tab(child, switch_to=False) -> Adds a new tab and 
        switches to it if switch_to is True. 
        
        """

        if not switch_to:
            index = self.get_current_page()+1
        else:
            index = -1

        self.add_tab(child, title=child.get_title(), icon=child.get_icon(), 
                index=index, switch_to=switch_to)

    def add_tab(self, child, title, icon=None, index=-1, switch_to=False):
        """ add_tab(child, title, icon=None, index=-1, switch_to=False) ->
        Insert a new tab at 'index' containing 'child.'  Give the new tab 
        a title made from 'title', and 'icon.'  Save the state of 'switch_to.'

        """

        self._switch_new_tab = switch_to
        self.insert_page(child, self.new_tab_label(title, icon=icon), index)

    def new_tab_label(self, title='Blank page', icon=None, max_width=18):
        """ new_tab_label(title='Blank page', icon=None, max_width=18) ->
        Make a new label containing an icon and title.  Make the new label
        'max_width' wide.

        """

        # Set up the label to look nice.
        label = gtk.Label(title)
        label.set_justify(gtk.JUSTIFY_LEFT)
        label.set_alignment(xalign=0, yalign=0.5)
        label.set_width_chars(max_width)
        label.set_max_width_chars(max_width)
        label.set_ellipsize(pango.ELLIPSIZE_END)

        # Add the icon.
        hbox = gtk.HBox(homogeneous=False, spacing=6)
        if not icon:
            icon = gtk.Image()
        hbox.pack_start(icon, False)
        hbox.pack_end(label, True, True)

        eventbox = gtk.EventBox()
        eventbox.add(hbox)
        eventbox.show_all()
        eventbox.set_has_window(False)

        return eventbox

    def set_tab_text(self, child, text):
        """ set_tab_text(child, text) -> Set the text on childs tab label to
        'text.'

        """

        eventbox = self.get_tab_label(child)
        if eventbox:
            eventbox.set_tooltip_text(text)
            eventbox.get_children()[0].get_children()[-1].set_text(text)
            self.set_menu_label_text(child, text)

    def set_tab_icon(self, child, icon):
        """ set_tab_icon(child, icon) -> Set the icon on the childs tab label
        to 'icon.'

        """

        eventbox = self.get_tab_label(child)
        if eventbox:
            tab_icon = eventbox.get_children()[0].get_children()[0]
            self._icon_from_image(icon, tab_icon)

    def set_tab_state(self, tab, state):
        """ set_tab_state(tab, state) -> Set the tab state based on 'state.'
        Minimize the tab if state is 'M', hide the tab if state is 'H', and
        do nothing if state is 'N.'

        """

        if state == 'M':
            self.toggle_minimize_tab(tab)
        elif state == 'H':
            self.toggle_hide_tab(tab)
        else:
            pass

    def get_tab_state(self, tab):
        """ get_tab_state(tab) -> Return the state of the tab.  'M' if the 
        tab is minimized, 'H' if it is hidden, and 'N' if neither.

        """

        try:
            eventbox = self.get_tab_label(tab)
            label = eventbox.get_children()[0].get_children()[-1]
            minimized = not label.get_property('visible')

            hbox = eventbox.get_children()[0]
            hidden = not hbox.get_property('visible')
        except:
            return 'N'

        if hidden:
            return 'H'
        elif minimized:
            return 'M'
        else:
            return 'N'

    def get_tab_icon(self, child):
        """ get_tab_icon(child) -> If the child has a 'get_icon method then 
        use that to get the icon, otherwise use the icon on the tabs label.

        Returns the childs icon or the icon on its tabs label.

        """

        if hasattr(child, 'get_icon'):
            # Just use the icon provided by the tab.
            icon = child.get_icon()
        else:
            # We have to use the icon on the label.
            eventbox = self.get_tab_label(child)
            if eventbox:
                icon = eventbox.get_children()[0].get_children()[0]
        return icon

    def get_tab_text(self, child):
        """ get_tab_text(child) -> Returns the text on the tabs label.

        """

        eventbox = self.get_tab_label(child)
        if eventbox:
            return eventbox.get_children()[0].get_children()[-1].get_text()

    def get_tab_title(self, child):
        """ get_tab_title(child) -> If the child has a 'get_title' method
        use it to get the tabs title, otherwise use its label text.

        Returns the title of 'child', or its tabs label text.

        """

        if hasattr(child, 'get_title'):
            # Good the child provides its own title.
            title = child.get_title()
            if not title:
                title = self.get_tab_text(child)
        else:
            # Grab the tab label instead.
            title = self.get_tab_text(child)
        return title

    def _tab_button_released(self, eventbox, event, child):
        """ _tab_button_released -> When the mouse button is released after
        clicking on a tab either close the tab (if it was middle clicked), or
        popup the menu if it was right clicked.

        """

        if event.button == 2 or \
                (event.button == 1 and event.state & gtk.gdk.CONTROL_MASK):
            # Close the tab on a middle click and control click.
            self.close_tab(child)
        elif event.button == 3:
            # Build the default menu of all the open tabs.
            menu = self._build_popup(clicked_tab=child)

            # Add custom tab items.
            self._add_tab_menu_items(menu, child)
            menu.popup(None, None, None, event.button, event.time, None)

            # We have to return true or the tabbar button release method will
            # execute and we will get two menus.
            return True

    def _tab_button_pressed(self, eventbox, event, child):
        """ _tab_button_pressed -> Called when a mouse button is pressed on
        a tab.  Does nothing right now.

        """

        if event.button == 1 and event.state & gtk.gdk.CONTROL_MASK:
            # Return True so the clicked tab is not raised.
            return True

    def _icon_from_image(self, image, icon):
        """ _icon_from_image(image, icon) -> Set icon to a copy of image.

        """

        image_type = image.get_storage_type()
        if image_type == gtk.IMAGE_PIXBUF:
            icon.set_from_pixbuf(image.get_pixbuf())
        elif image_type == gtk.IMAGE_PIXMAP:
            icon.set_from_pixmap(*image.get_pixmap())
        elif image_type == gtk.IMAGE_ICON_NAME:
            icon.set_from_icon_name(*image.get_icon_name())
        elif image_type == gtk.IMAGE_STOCK:
            icon.set_from_stock(*image.get_stock())
        else:
            icon.set_from_image(*image.get_image())

    def _add_tab_menu_items(self, menu, clicked_tab):
        """ _add_tab_menu_items(menu) -> To be implemented by inheritor. 
        
        """

        pass

    def _build_popup(self, clicked_tab=None):
        """ _build_popup() -> Build the pop up menu.
        
        """

        menu = gtk.Menu()
        
        item_tup = (
                ('_minimize_tab_item', ('gtk-remove', 
                    '_Minimize/Unminimize Tab', True, '<Control>m', 
                    self._minimize_tab_button_released, (clicked_tab,))),
                ('_hide_tab_item', ('view-restore', '_Hide/Unhide Tab', True, 
                    '<Control>h', self._hide_tab_button_released, 
                    (clicked_tab,))),
                gtk.SeparatorMenuItem(),
                )

        accel_group = gtk.AccelGroup()
        menu.set_accel_group(accel_group)

        if clicked_tab:
            for menu_item in item_tup:
                if type(menu_item) == tuple:
                    item_name, (icon_name, label_text, is_sensitive, accel, 
                            clicked_callback, user_args) = menu_item
                    icon = gtk.Image()
                    icon.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)
                    item = gtk.ImageMenuItem()
                    item.set_image(icon)
                    item.set_label(label_text)
                    item.set_use_underline(True)
                    item.set_sensitive(is_sensitive)
                    item.connect('button-release-event', clicked_callback, 
                            *user_args)
                    if accel:
                        keyval, modifier = gtk.accelerator_parse(accel)
                        item.add_accelerator('activate', accel_group, keyval, 
                                modifier, gtk.ACCEL_VISIBLE)
                    self.__setattr__(item_name, item)
                else:
                    item = menu_item
                menu.insert(item, item_tup.index(menu_item))

        # Add each tab [icon, title] to menu
        for tab in self.get_children():
            icon = gtk.Image()

            # Get tab icon as image
            self._icon_from_image(self.get_tab_icon(tab), icon)
            text = self.get_tab_title(tab)
            item = gtk.ImageMenuItem()
            item.set_image(icon)
            item.set_label(text)
            label = item.get_children()[0]
            label.set_max_width_chars(48)
            label.set_ellipsize(pango.ELLIPSIZE_END)

            if tab == self._current_tab:
                # Current tab title should be bold italic
                label.modify_font(pango.FontDescription('bold italic'))
            item.connect('button-release-event', 
                    self._popup_item_button_released, tab, menu)
            menu.add(item)
        menu.show_all()

        return menu

    def _minimize_tab_button_released(self, close_tab_item, event, 
            clicked_tab):
        """ _minimize_tab_button_released -> Hide the icon of the clicked tab.

        """

        self.toggle_minimize_tab(clicked_tab)

    def _hide_tab_button_released(self, close_tab_item, event, clicked_tab):
        """ _hide_tab_button_released -> Hide the the label and icon of the 
        clicked tab.

        """
        self.toggle_hide_tab(clicked_tab)

    def _popup_item_button_released(self, item, event, child, menu):
        """ _popup_item_button_released -> Switch to the tab that was
        selected from the popup menu.

        """

        menu.popdown()
        self.set_current_page(self.page_num(child))

    def _page_added_callback(self, tabbar, child, index):
        """ _page_added_callback -> When a page is added make it reorderable,
        and connect to some of its labels signals.  If the switch_new_tab
        variable is True the switch to and grab the focus of the new tab.

        """

        # Get the label and connect to its button press and release events.
        eventbox = self.get_tab_label(child)
        eventbox.connect('button-release-event', self._tab_button_released, 
                child)
        eventbox.connect('button-press-event', self._tab_button_pressed, child)
        self.set_tab_reorderable(child, True)

        # If we are switching to the new page set the input focus to the
        # new child.
        if self._switch_new_tab:
            self.set_current_page(index)
            child.grab_focus()

        # Make the tabs visible if more than one are open.
        if tabbar.get_n_pages() > 1 and self._toggle_tabs:
            self.set_show_tabs(True)

        self.emit('tab-added', child)

    def _page_removed_callback(self, tabbar, child, index):
        """ _page_removed_callback -> Remove the closed tab from the previous
        tab list.  If the last page was closed exit.

        """

        if self.get_n_pages() == 0:
            self.emit('exit')

        # We are not going to need to switch to this tab anymore, so remove
        # it from the list.
        while child in self._previous_tab:
            self._previous_tab.remove(child)

        # Hide the tabs if fewer than one tab is open.
        if tabbar.get_n_pages() < 1 and self._toggle_tabs:
            self.set_show_tabs(False)

    def _page_switched_callback(self, tabbar, page, index):
        """ _page_switched_callback -> After switching to a new tab add the
        previous tab to the previous tab list, and tell anybody listening
        that their title should change.

        """

        # The last tab is the next one in line to switch to when this one is 
        # closed.
        if self._current_tab in self.get_children():
            self._previous_tab.append(self._current_tab)
            if hasattr(self._current_tab, 'active_tab'):
                self._current_tab.active_tab = False

        self.set_property('current-page', self.get_nth_page(index))
        title = self.get_tab_title(self._current_tab)
        self.emit('title-changed', title)

        if hasattr(self._current_tab, 'active_tab'):
            self._current_tab.active_tab = True
            self._current_tab.take_focus()

    def _tabbar_button_press(self, tabbar, event):
        """ _tabbar_button_press -> Open a new tab if the tabbar was double 
        clicked.

        """

        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.emit('new-tab', event.state, self._current_tab)

    def _tabbar_button_release(self, tabbar, event):
        """ _tabbar_button_release -> Popup the tabbar menu if the tabbar was
        right clicked.

        """

        if event.button == 3:
            menu = self._build_popup()
            menu.popup(None, None, None, event.button, event.time, None)

class TerminalTabs(TabBase):
    """ TerminalTabs(show_tabs) -> Inherits TabBase 
    
    """

    def __init__(self, show_tabs=True, action_widget=None):
        """ TerminalTabs(show_tabs) -> Tabs for a terminal.
        
        """

        super(TerminalTabs, self).__init__(show_tabs, action_widget)

        self._terminal = None

    def new_terminal(self, directory, command=None, argv=[], 
            title="Debug Console", enable_input=False):
        """ new_terminal(directory, command=None, argv=[], 
        title="Debug Console", enable_input=False) ->
        Adds a new terminal tab based in directory running command with args 
        argv and title enable/disable input.
        
        """

        terminal = TermBox(directory, command, argv, enable_input)
        terminal.connect('hide-term', self._hide_term)
        terminal.connect('title-changed', self._term_title_changed)
        icon = gtk.Image()
        icon.set_from_icon_name('utilities-terminal', gtk.ICON_SIZE_MENU)
        self.add_tab(terminal, title, icon=icon)

        return terminal

    def _term_title_changed(self, child, title):
        """ _term_title_changed(child, title) -> Called when the terminals
        title changes.  Sets the tab label and emits the title-changed signal
        if child is the current tab.

        """

        self.set_tab_text(child, title)
        if self.get_current_page() == self.page_num(child):
            self.emit('title-changed', title)

    def _hide_term(self, terminal, hide_menuitem):
        """ _hide_term -> Hide all the tabs.

        """

        self.toggle_visible()

    def _toggle_terminal(self, menu_item, event):
        """ Add/Remove a terminal from the tab box.

        """

        if self._terminal:
            self.close_tab(self._terminal, force=True)
            self._terminal = None
        else:
            self._terminal = self.new_terminal(
                    os.getenv('HOME'), command=os.getenv('SHELL'),
                    title='Shell Terminal', enable_input=True)

    def _add_tab_menu_items(self, menu, clicked_tab):
        """ Add some extra menu items.

        """

        item_tup = (
                ('_add_term', ('utilities-terminal', 'Add/Remove _Terminal', 
                    True, None, self._toggle_terminal, ())),
                gtk.SeparatorMenuItem(),
                ('_hide_item', ('gtk-remove', 'H_ide', True, None, 
                    lambda *a: self.toggle_visible(), ())), 
                gtk.SeparatorMenuItem(),
                )

        accel_group = gtk.AccelGroup()
        menu.set_accel_group(accel_group)

        for menu_item in item_tup:
            if type(menu_item) == tuple:
                item_name, (icon_name, label_text, is_sensitive, accel, 
                        clicked_callback, user_args) = menu_item
                icon = gtk.Image()
                icon.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)
                item = gtk.ImageMenuItem()
                item.set_image(icon)
                item.set_label(label_text)
                item.set_use_underline(True)
                item.set_sensitive(is_sensitive)
                item.connect('button-release-event', clicked_callback, 
                        *user_args)
                if accel:
                    keyval, modifier = gtk.accelerator_parse(accel)
                    item.add_accelerator('activate', accel_group, keyval, 
                            modifier, gtk.ACCEL_VISIBLE)
                self.__setattr__(item_name, item)
            else:
                item = menu_item
            menu.insert(item, item_tup.index(menu_item))

        menu.show_all()

class BrowserTabs(TabBase):
    """ BrowserTabs(show_tabs=True) -> Inherits TabBase 
    
    """

    __gsignals__ = {
            'duplicate-tab' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (object, object)), 
            'paste-tab' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT)),
            }

    def __init__(self, tabs_file, show_tabs=True, action_widget=None):
        """ BrowserTabs(tabs_file, show_tabs=True) -> Tabs for Browser.
        tabs_file - The filename of the file to save the tab information to.
        show_tabs - If True then show the tabs otherwise hide them.
        
        """

        super(BrowserTabs, self).__init__(show_tabs, action_widget)

        self._current_folder = os.getenv('HOME')
        self._tabs_file = tabs_file
        self.connect('page-added', self._browser_added)
        self.connect('drag-motion', self._drag_motion)
        self.connect('drag-data-received', self._drag_data_received)
        self.connect('drag-drop', self._drag_drop)
        self.connect('drag-begin', self._drag_begin)

        drag_accept_tup = [
                ('text/plain', 0, 0), 
                ('GTK_NOTEBOOK_TAB', gtk.TARGET_SAME_APP, 1)
                ]
        self.drag_dest_set(gtk.DEST_DEFAULT_ALL,
                drag_accept_tup, 
                gtk.gdk.ACTION_COPY)
        self.set_group_id(1)
        self._dragged_data = None

    def _drag_begin(self, tabbar, context):
        """ When a tab is being dragged out, disconnect it's signal handlers
        so it won't be handled by this tabbar.

        """

        # Get the label and disconnect from its button press and release 
        # events.
        eventbox = self.get_tab_label(self._current_tab)
        try:
            eventbox.disconnect_by_func(self._tab_button_released)
            eventbox.disconnect_by_func(self._tab_button_pressed)
        except TypeError:
            pass
        self._connect_browser(self._current_tab, disconnect=True)

    def _drag_data_received(self, tabbar, context, x, y, selection, 
            targettype, timestamp):
        """ Check the received data.  If it is a string than save it and open 
        a new tab otherwise do nothing.

        """

        if y <= 16 and targettype == 0:
            self._dragged_data = selection.data
            self.emit('new-tab', 0, None)
            return True
        elif targettype == 1:
            return True

        return False

    def _drag_motion(self, tabbar, context, x, y, timestamp):
        """ When something is dragged over check if it is over the tab
        area and handle it accordingly.

        """

        if y <= 16:
            return False
        else:
            return True

    def _drag_drop(self, tabbar, context, x, y, timestamp):
        """ Handle drops.

        """

        return True

    def new_tab(self, browsebox, switch_to=False):
        """ new_browser(browsebox, switch_to=False) -> adds a new tab for
        browser 'browsebox' and switches to it if switch_to is True. 
        
        """

        # Run the parent method.
        super(BrowserTabs, self).new_tab(browsebox, switch_to)

    def _connect_browser(self, browsebox, disconnect=False):
        """ Connect/disconnect signal handlers to the browsebox.

        """

        connection_dict = {
                'title-changed': self._browser_title_changed,
                'save-tabs' : self._handle_save_tabs,
                }
        for signal, callback in connection_dict.iteritems():
            if gobject.signal_lookup(signal, browsebox):
                if disconnect:
                    try:
                        self._current_tab.connect(signal, callback)
                    except:
                        pass
                else:
                    browsebox.connect(signal, callback)

    def _browser_added(self, tabbar, browsebox, index):
        """ Connect browsebox signals to handlers.

        """

        self._connect_browser(browsebox)

        if self._dragged_data:
            browsebox.load_uri(self._dragged_data)
            self._dragged_data = None

        if browsebox.type != 'BrowserSock':
            self.set_tab_detachable(browsebox, True)

    def _browser_title_changed(self, browsebox, title):
        """ Change the tab label and emit 'title-changed' signal when the
        title of the tab changes.

        """

        if hasattr(browsebox, 'get_pid'):
            self.set_tab_text(browsebox, '%s (pid: %d)' % (title, 
                browsebox.get_pid()))
        else:
            self.set_tab_text(browsebox, title)
        if self.get_current_page() == self.page_num(browsebox):
            self.emit('title-changed', title)

    def _add_tab_menu_items(self, menu, clicked_tab):
        """ Add the browser specific menu items to the tab bar menu.

        """

        clipboard = gtk.clipboard_get('CLIPBOARD')
        has_text = clipboard.wait_is_text_available()
        
        item_tup = (
                ('_new_tab_item', ('tab-new', '_New Tab', True, '<Control>t', 
                    self._add_tab_button_released, (clicked_tab,))),
                #('_new_back_tab_item', ('tab-new-background', 
                    #'New _Background Tab', True, None, 
                    #self._add_back_tab_button_released, (clicked_tab,))),
                ('_duplicate_tab_item', ('edit-copy', '_Duplicate Tab', 
                    True, None, self._duplicate_tab_button_released, 
                    (clicked_tab,))),
                gtk.SeparatorMenuItem(),
                ('_close_tab_item', ('gtk-remove', '_Close Tab', True, 
                    '<Control>w', self._close_tab_button_released, 
                    (clicked_tab,))),
                ('_close_other_item', ('gtk-close', 
                    'Close _Other Tabs', True, '<Control><Alt>w', 
                    self._close_other_button_released, (clicked_tab,))),
                ('_close_all_item', ('gtk-clear', 'Close _All Tabs', True, 
                    '<Control><Shift>w', self._close_all_button_released, 
                    (clicked_tab,))),
                gtk.SeparatorMenuItem(),
                ('_save_tabs_item', ('gtk-save', '_Save Tabs', True, None,
                    self._save_tabs_button_released, ())),
                ('_copy_tab_item', ('gtk-copy', 'C_opy Tab', True, None,
                    self._copy_tab_button_released, (clicked_tab,))),
                ('_copy_all_item', ('gtk-copy', 'Copy A_ll Tabs', True, None,
                    self._copy_all_button_released, ())),
                ('_paste_tab_item', ('gtk-paste', '_Paste Tab', has_text, None,
                    self._paste_tab_button_released, (clicked_tab,))),
                gtk.SeparatorMenuItem(),
                )

        accel_group = gtk.AccelGroup()
        menu.set_accel_group(accel_group)

        for menu_item in item_tup:
            if type(menu_item) == tuple:
                item_name, (icon_name, label_text, is_sensitive, accel, 
                        clicked_callback, user_args) = menu_item
                icon = gtk.Image()
                icon.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)
                item = gtk.ImageMenuItem()
                item.set_image(icon)
                item.set_label(label_text)
                item.set_use_underline(True)
                item.set_sensitive(is_sensitive)
                item.connect('button-release-event', clicked_callback, 
                        *user_args)
                if accel:
                    keyval, modifier = gtk.accelerator_parse(accel)
                    item.add_accelerator('activate', accel_group, keyval, 
                            modifier, gtk.ACCEL_VISIBLE)
                self.__setattr__(item_name, item)
            else:
                item = menu_item
            menu.insert(item, item_tup.index(menu_item))

        menu.show_all()

    def _add_tab_button_released(self, add_tab_item, event, clicked_tab):
        """ Notify the browser to open a new tab.

        """

        self.emit('new-tab', event.state, clicked_tab)

    def _add_back_tab_button_released(self, add_back_tab_item, event, 
            clicked_tab):
        """ Ask the browser to open a new tab in the background.

        Not implemented.

        """

        self.emit('new-tab', event.state, clicked_tab)

    def _save_tabs_button_released(self, save_tabs_item, event):
        """ _save_tabs_button_released -> Save the open tabs to a user 
        selected file.

        """

        # Open a file dialog so the user can select the file to export to.
        save_dialog = SaveDialog('tabs_list', self._current_folder)
        out_filename = save_dialog.run()

        # Set the current_folder to the parent of the file selected.
        self._current_folder = save_dialog.get_folder()

        # Save the open tabs if a file was selected.
        if out_filename:
            self.save_tabs(out_filename)

    def _copy_tab_button_released(self, copy_tab_item, event, clicked_tab):
        """ _copy_tab_button_released -> Copy the information about the
        clicked tab.

        """

        self._copy_tab_list((clicked_tab,))

    def _copy_all_button_released(self, copy_all_item, event):
        """ _copy_all_button_released -> Copy the information about the
        all the tabs.

        """

        self._copy_tab_list(self.get_children())

    def _paste_tab_button_released(self, copy_tab_item, event, clicked_tab):
        """ _paste_tab_button_released -> Emit the 'paste-tab' signal so the
        browser will paste the tab in the clipboard after clicked_tab.

        """

        self.emit('paste-tab', clicked_tab, event.state)

    def _duplicate_tab_button_released(self, duplicate_tab_item, event, 
            clicked_tab):
        """ _duuplicate_tab_button_released -> Ask the browser to duplicate
        the clicked tab.

        """

        self.emit('duplicate-tab', event.state, clicked_tab)

    def _close_all_button_released(self, close_all_item, event, clicked_tab):
        """ _close_all_button_released -> Close all the tabs and open a new
        tab.

        """

        tab_list = self.get_children()
        tab_list.reverse()
        glib.idle_add(self._close_list, tab_list, clicked_tab)
        self.emit('new-tab', event.state, clicked_tab)
        self.close_tab(clicked_tab)

    def _close_other_button_released(self, close_other_item, event, 
            clicked_tab):
        """ _close_ther_button_released -> Close all the tabs except the tab
        that was right clicked.

        """

        tab_list = self.get_children()
        tab_list.reverse()
        glib.idle_add(self._close_list, tab_list, clicked_tab)

    def _close_tab_button_released(self, close_tab_item, event, clicked_tab):
        """ _close_tab_button_released -> Close the clicked tab.

        """

        self.close_tab(clicked_tab)

    def _close_list(self, tab_list, clicked_tab):
        """ _close_list(tab_list, clicked_tab) -> Close all the tabs except
        'clicked_tab.'

        """

        for tab in tab_list:
            if tab != clicked_tab:
                self.close_tab(tab)

    def _copy_tab_list(self, tab_list):
        """ _browser_book_copy_tab(browser_book, tab_list) -> Copy the 
        information from all the tabs in 'tab_list.'

        """

        info_list = []
        for tab in tab_list:
            info = self.get_tab_info(tab)
            if info:
                info_list.append(info)

        clipboard = gtk.clipboard_get('CLIPBOARD')
        clipboard.set_text(json.dumps(info_list, indent=4))
        clipboard.store()

    def get_tab_info(self, tab):
        """ get_tab_info(tab) -> Return a list containing all the info
        about a tab.

        The format of the tab info is as follows:

        Old:
        [pid, tab_state, [history_index, [[title, uri], [title, uri], ...]]]...

        New:
        {
            'pid': pid,
            'state': tab_state,
            'history':  [
                            history_index,
                            [
                                [title, uri],
                                [title, uri].
                                ...
                            ]
                        ]
        }
        
        """

        if not hasattr(tab, 'get_save_dict'):
            return None

        info_dict = tab.get_save_dict()

        if not info_dict['history']:
            return None

        tab_state = self.get_tab_state(tab)
        info_dict['state'] = tab_state

        return info_dict

    def _handle_save_tabs(self, *args):
        """ Save the tabs.

        """

        self.save_tabs()

    def save_tabs(self, filename=None, exclude=()):
        """ save_tabs(filename=None, exclude=()) -> Save the history, type, 
        and state (minimized, hidden, or normal) of all the tabs, except the 
        ones in the 'exclude' tuple, to a file so they can be restored later.

        A list is filled items formated as follows:

        [pid, tab_state, [history_index, [[title, uri], [title, uri], ...]]]...

        Finally the list is dumped to a formated string, and written to a file.

        """

        if not filename:
            filename = self._tabs_file

        info_list = []
        for tab in self.get_children():
            # Skip the tabs in the exclude tuple.
            if tab in exclude:
                continue

            info = self.get_tab_info(tab)
            # Only save tabs that are not blank.
            if info:
                info_list.append(info)

        # Dump the tab info to a formated string and write it to a file.
        save_str = json.dumps(info_list, indent=4)
        with open(filename, 'w') as tabs_file:
            tabs_file.write(save_str.strip())

        return True

class TabList(gtk.ScrolledWindow):
    """ TabList -> A List to hold closed tabs.

    """

    __gsignals__ = {
            'reopen-tab' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
                (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT)),
            }

    def __init__(self):
        """ TabList -> A list view for holding the history of the tabs that 
        were closed.

        """

        super(TabList, self).__init__()

        # Set the title that TabBase class will display on the tab this 
        # object will be added to.
        self._title = "Closed Tabs"

        # Set the icon that TabBase class will display on the tab this 
        # object will be added to.
        self._icon = gtk.Image()
        self.set_icon('document-open-recent')

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
                ('Icon', gtk.CellRendererPixbuf(), {'pixbuf':0}, False, 
                    gtk.gdk.Pixbuf),
                ('Title', gtk.CellRendererText(), {'text':1}, True, str),
                ('URI', gtk.CellRendererText(), {'text':2}, True, str),
                )

        # Create a treeview and make set it to allow multiple selections
        # and rubber band selections.
        self._tab_view = gtk.TreeView()
        self._tab_view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self._tab_view.set_rubber_banding(True)

        col_types = []

        # Build the columns for the treeview.
        for (title, renderer, value, resizable, col_type) in column_tup:
            column = gtk.TreeViewColumn(title, renderer, **value)
            column.set_resizable(resizable)
            self._tab_view.append_column(column)

            # Collect the data types for each column.
            col_types.append(col_type)

        # Add some extra non-visible column data types.  These columns are
        # used to hold the pid, tab_index, history_index, and history_list 
        # of each tab.
        col_types.extend((str, object))

        # Create the liststore using the data types in col_types list.
        self._tab_store = gtk.ListStore(*col_types)
        self._tab_view.set_model(self._tab_store)

        self._tab_view.connect('button-release-event', self._view_button_released)
        self._tab_view.connect('key-press-event', self._view_key_pressed)

        # The pop-up menu. 
        self._menu = self._build_menu()

        self.add(self._tab_view)
        self.show_all()

    def _build_menu(self):
        """ _build_menu() -> Build the pop-up menu.

        """

        menu = gtk.Menu()

        # A tuple to hold the information used to make each menu item.
        # Format:
        # (item_name, (icon_name, label_text, enabled, accel, callback))
        item_tup = (
                ('_import_list_item', ('gtk-open', '_Import List', 
                    True, None, self._import_list_button_released)),
                ('_export_list_item', ('gtk-save', '_Export List', 
                    False, None, self._export_list_button_released)),
                gtk.SeparatorMenuItem(),
                ('_reopen_tab_item', ('document-open', '_Re-Open Selected', 
                    False, None, self._reopen_tab_button_released)),
                ('_reopen_all_item', ('document-open', 'Re-Open _All', 
                    False, None, self._reopen_all_button_released)),
                gtk.SeparatorMenuItem(),
                ('_copy_uri_item', ('edit-copy', '_Copy Uri', 
                    False, None, self._copy_uri_button_released)),
                ('_copy_tab_item', ('edit-copy', 'Copy _Selected Tabs',
                    False, None, self._copy_tab_button_released)),
                gtk.SeparatorMenuItem(),
                ('_remove_tab_item', ('list-remove', 'Remove _Selected', 
                    False, 'Delete', self._remove_tab_button_released)),
                ('_clear_item', ('gtk-clear', 'C_lear List', 
                    False, None, self._clear_button_released)),
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

    def _view_button_released(self, tab_view, event):
        """ _view_button_released -> Called when the mouse button is released
        on the tab list. 
        
        """

        # Get the item that is under the mouse
        path = tab_view.get_path_at_pos(int(event.x), int(event.y))
        selection = tab_view.get_selection()
        if path:
            # Select the item under the mouse if one or fewer items are 
            # selected.
            if selection.count_selected_rows() <= 1 and event.button == 3 \
                    or event.button == 2:
                selection.unselect_all()
                selection.select_path(path[0])

            # Enable the copy_uri item when the mouse is over an item
            self._reopen_tab_item.set_sensitive(True)
            self._copy_uri_item.set_sensitive(True)
            self._copy_tab_item.set_sensitive(True)
            self._remove_tab_item.set_sensitive(True)
        else:
            # Disable the reopen, remove, and copy_uri items when the 
            # mouse is not over an item in the list
            self._reopen_tab_item.set_sensitive(False)
            self._copy_uri_item.set_sensitive(False)
            self._copy_tab_item.set_sensitive(False)
            self._remove_tab_item.set_sensitive(False)

            selection.unselect_all()
            
        if event.button == 3:
            # Enable/Disable the clear_item and reopen_all_item based on 
            # whether the tab list is empty or not
            self._clear_item.set_sensitive(len(self._tab_store) > 0)
            self._reopen_all_item.set_sensitive(len(self._tab_store) > 0)
            self._export_list_item.set_sensitive(len(self._tab_store) > 0)

            # Pop up menu
            self._menu.popup(None, None, None, event.button, event.time, None)

            return True
        elif event.button == 2:
            # Remove the item under the mouse from the list when the 
            # middle mouse button is clicked
            self._remove_selected()

            return True

        return False

    def _view_key_pressed(self, tab_view, event):
        """ _view_key_pressed -> Called when a key is pressed on the tab list.
        
        """

        if event.keyval == gtk.gdk.keyval_from_name('Delete'):
            self._remove_selected()
            return True

        return False

    def _import_list_button_released(self, import_list_item, event):
        """ _import_list_button_released -> Import a tab list from a file.

        """

        # Open a file dialog so the user can select a file to import.
        open_dialog = OpenDialog(self._current_folder)
        in_filename = open_dialog.run()

        # Set the current_folder to the parent of the file selected.
        self._current_folder = open_dialog.get_folder()

        # Import the tabs from the file if one was selected.
        if in_filename:
            # Start a thread to import the list from in_filename.
            self.import_list(in_filename)

    def _export_list_button_released(self, export_list_item, event):
        """ _export_list_button_released -> Export the tab list to a file.

        """

        # Open a file dialog so the user can select the file to export to.
        save_dialog = SaveDialog('tabs_list', self._current_folder)
        out_filename = save_dialog.run()

        # Set the current_folder to the parent of the file selected.
        self._current_folder = save_dialog.get_folder()

        # Export the tabs from the file if one was selected.
        if out_filename:
            info_list = []
            for row in self._tab_store:
                iter = row.iter
                info_list.append(self._get_info_list(iter))

            # Dump all the tab information to a string.
            save_str = json.dumps(info_list, indent=4)

            with open(out_filename, 'w') as tabs_file:
                # Write the tab string to the selected file.
                tabs_file.write(save_str.strip())

    def _clear_button_released(self, clear_item, event):
        """ _clear_button_released -> Clear the list.

        """

        for row in self._tab_store:
            iter = row.iter
            self._remove_item(iter)

    def _reopen_tab_button_released(self, reopen_tab_item, event):
        """ _reopen_tab_button_released -> Loop through all the selected
        tabs and emit the 'reopen-tab' signal so the browser can open
        each one.  Provide the key-flags information so the tabs can be
        opened based on that.

        """

        reopen_tab_item.parent.popdown()

        selection = self._tab_view.get_selection()

        glib.idle_add(self._reopen_list, selection.get_selected_rows()[1], 
                event.state)

    def _reopen_all_button_released(self, reopen_all_item, event):
        """ _reopen_all_button_released -> Send all the tabs in the list
        to the browser to open.

        """

        reopen_all_item.parent.popdown()

        glib.idle_add(self._reopen_list, self._tab_store, event.state)

    def _reopen_list(self, tab_list, flags):
        """ _reopen_list(tab_list, flags) -> Send all the tabs in tab_list 
        to the browser to be opened.

        """

        def reopen_list(tab_list, flags):
            for row in tab_list:
                if type(row) == tuple:
                    iter = self._tab_store.get_iter(row)
                else:
                    iter = row.iter
                tab_dict = self._get_tab_dict(iter)
                self.emit('reopen-tab', tab_dict, flags)

        reopen_thread = threading.Thread(target=reopen_list, 
                args=(tab_list, flags))
        reopen_thread.daemon = True
        reopen_thread.start()

    def _remove_tab_button_released(self, remove_tab_item, event):
        """ _remove_tab_button_released -> Remove the selected tabs.
        
        """

        remove_tab_item.parent.popdown()
        
        self._remove_selected()

    def _copy_uri_button_released(self, copy_item, event):
        """ _copy_uri_button_released -> Loop through all the selected tabs
        and create a string with each uri separated by '\n' a new line and
        copy that to the clipboard.

        """

        selection = self._tab_view.get_selection()
        uri_list = []
        for row in selection.get_selected_rows()[1]:
            iter = self._tab_store.get_iter(row)
            uri_list.append(self._get_uri(iter))

        clipboard = gtk.clipboard_get('CLIPBOARD')
        clipboard.set_text('\n'.join(uri_list))
        clipboard.store()

    def _copy_tab_button_released(self, copy_tab_item, event):
        """ _copy_tab_button_released -> Loop through all the selected items
        and combine the info lists from each one, separating them by a new-line
        character.  Then store them in the clipboard.

        """

        selection = self._tab_view.get_selection()
        info_list = []
        for row in selection.get_selected_rows()[1]:
            iter = self._tab_store.get_iter(row)
            info_list.append(self._get_info_list(iter))

        clipboard = gtk.clipboard_get('CLIPBOARD')
        clipboard.set_text(json.dumps(info_list, indent=4))
        clipboard.store()

    def _remove_item(self, iter):
        """ _remove_item -> Remove the item pointed to by iter.

        """

        self._tab_store.remove(iter)

    def _remove_selected(self):
        """ _remove_selected -> Remove all the selected tabs.

        """

        selection = self._tab_view.get_selection()

        row_list = selection.get_selected_rows()[1]
        row_list.reverse()
        for row in row_list:
            iter = self._tab_store.get_iter(row)
            self._remove_item(iter)

    def _get_tab_dict(self, iter):
        """ _get_tab_dict(iter) -> Return a dictionary of all the information
        from the item pointed to by iter.

        """

        index = self._get_index(iter)
        info_list = self._get_info_list(iter)

        return {'info_list':info_list, 'index':index}

    def _get_title(self, iter):
        """ _get_title(iter) -> Return the title of the item pointed to by
        iter.

        """

        return self._tab_store.get_value(iter, 1)

    def _get_uri(self, iter):
        """ _get_uri(iter) -> Return the uri of the item pointed to by
        iter.

        """

        return self._tab_store.get_value(iter, 2)

    def _get_index(self, iter):
        """ _get_index(iter) -> Return the index of the item pointed to by
        iter.

        """

        return self._tab_store.get_value(iter, 3)

    def _get_info_list(self, iter):
        """ _get_info_list(iter) -> Return the tab info in list form for
        the item pointed to by iter.

        """

        return self._tab_store.get_value(iter, 4)

    def _set_title(self, iter, title):
        """ _set_title(iter, title) -> Set the title of the item pointed to 
        by iter to 'title.'

        """

        self._tab_store.set_value(iter, 1, title)

    def _set_uri(self, iter, uri):
        """ _set_uri(iter, uri) -> Set the uri of the item pointed to by 
        iter to 'uri.'

        """

        self._tab_store.set_value(iter, 2, uri)

    def import_list(self, filename):
        """ import_list(filename) -> Start a thread to import a list of tabs 
        from a file.

        """

        import_thread = threading.Thread(target=self._import_list_thread,
                args=(filename,))
        import_thread.daemon = True
        import_thread.start()

    def _import_list_thread(self, filename):
        """ _import_list_thread(filename) -> Import a list of tabs from a file.

        The format of the tab file is as follows:

        Old:
        [pid, tab_state, [history_index, [[title, uri], [title, uri], ...]]]...

        New:
        {
            'pid': pid,
            'state': tab_state,
            'history':  [
                            history_index,
                            [
                                [title, uri],
                                [title, uri].
                                ...
                            ]
                        ]
        }

        One for each item of a list and all of it is dumped to a file.

        """

        # Exit if the file does not exist.
        if not os.path.isfile(filename):
            return False

        with open(filename, 'r') as tabs_file:
            info_str = tabs_file.read()

        try:
            for (tab_index, info_list) in enumerate(json.loads(info_str)):
                # Check for new or old info.
                if isinstance(info_list, dict):
                    # It is new.
                    tab_pid = info_list['pid']
                    tab_state = info_list['state']
                    hist_list = info_list['history']
                else:
                    # It is old.
                    tab_pid, tab_state, hist_list = info_list

                # Skip the tab if it has no hist_list, because it is blank.
                if not hist_list:
                    continue

                # Just use a default icon, because the file doesn't
                # define icons.
                icon_theme = gtk.icon_theme_get_default()
                icon = icon_theme.load_icon('text-html', 
                        gtk.ICON_SIZE_MENU, 
                        gtk.ICON_LOOKUP_USE_BUILTIN)

                # Add the information about the tab to the list.
                self.add_tab(icon, info_list, tab_index)
        except:
            # It is an old style file.
            for (tab_index, line) in enumerate(info_str.splitlines()):
                # Get the pid and the string containing the history 
                # index and tab history.
                info_list = json.loads(line)

                # Check if it is an old style file.
                if type(info_list[-1]) == unicode:
                    old_file = True
                    tab_pid, hist_str = info_list
                else:
                    old_file = False
                    tab_pid, tab_state, hist_list = info_list
                    hist_str = json.dumps(hist_list)

                # If the history string is empty than the tab is blank 
                # and should just be dropped.
                if hist_str:
                    # Just use a default icon, because the file doesn't
                    # define icons.
                    icon_theme = gtk.icon_theme_get_default()
                    icon = icon_theme.load_icon('text-html', 
                            gtk.ICON_SIZE_MENU, 
                            gtk.ICON_LOOKUP_USE_BUILTIN)

                    # Add the information about the tab to the list.
                    self.add_tab(icon, info_list, tab_index)

    def add_tab(self, icon, info_list, index):
        """ add_tab(icon, info_list, index) -> Add an event 
        to add a closed tab to the list when the main glib thread is idle.

        """

        glib.idle_add(self._add_tab, icon, info_list, index)
    
    def _add_tab(self, icon, info_list, index):
        """ _add_tab(icon, info_list, index) -> Add a new item to the list.

        """

        if isinstance(info_list, dict):
            # It is the new type:
            # Load the history index and tab history.
            hist_index, tab_hist = info_list['history']
        else:
            # It is a list.

            # Check if it is an old list.
            if type(info_list[-1]) == unicode:
                old_file = True
                tab_pid, hist_str = info_list
            else:
                old_file = False
                tab_pid, tab_state, (hist_index, tab_hist) = info_list

            if old_file:
                # It is an old list so add a nothing state.
                info_list.insert(1, 'N')

                # Load the history index and tab history.
                hist_index, tab_hist = json.loads(hist_str)
                hist_index = int(hist_index)

                # Make the info list like a new one.
                info_list.append(json.loads(info_list.pop()))

        if tab_hist:
            if hist_index != 1:
                title, uri = tab_hist[(len(tab_hist) - 1) + hist_index]
            else:
                title, uri = tab_hist[-1]
        else:
            title, uri = ('Blank', 'about:blank')

        self._tab_store.append((icon, title.strip(), uri.strip(), index, 
            info_list))

        # Scroll the the last item.
        self._tab_view.scroll_to_cell((len(self._tab_store) - 1,))

        return False

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

