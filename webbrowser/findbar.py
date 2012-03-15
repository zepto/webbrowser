# This file is part of browser, and contains a find_bar object.
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

""" This module provides a toolbar to be used for searching for text in
a textview or webview.

"""

import gtk
import gobject

class FindBar(gtk.Toolbar):
    """ FindBar a toolbar used for specifying what text to find and what
    settings to use to find it in a webview or textview.

    """

    # Defing custom gobject signals.
    __gsignals__ = {
            'find-next' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (gobject.TYPE_STRING,)),
            'find-previous' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (gobject.TYPE_STRING,)),
            'highlight-toggled' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (gobject.TYPE_BOOLEAN,)),
            'match-case-toggled' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (gobject.TYPE_BOOLEAN,)),
            }

    def __init__(self):
        """ FindBar -> A toolbar used for finding text in a textview or
        webview.

        """

        super(FindBar, self).__init__()
        
        self._build()

        # Setup the orientation and the size of the toolbar
        self.set_style(gtk.TOOLBAR_BOTH_HORIZ)
        self.set_icon_size(gtk.ICON_SIZE_MENU)
        
        # Automatically stay hidden.
        self.set_no_show_all(True)

    def _build(self):
        """ _build -> Build and configure the toobar.

        """

        # Create a label for the text entry.
        find_label = gtk.Label('Find:')

        # Setup the find entry
        self._find_entry = gtk.Entry()
        self._find_entry.set_width_chars(50)
        self._find_entry.set_icon_from_icon_name(0, 'gtk-find') 
        self._find_entry.set_icon_from_icon_name(1, 'gtk-clear') 
        self._find_entry.set_tooltip_text("Enter find string here")
        self._find_entry.set_icon_tooltip_text(1, 'Clear find string')
        self._find_entry.connect('activate', self.find_on_page)
        self._find_entry.connect('icon-release', self._find_icon_release)
        self._find_entry.connect('changed', self._find_entry_changed)

        # Make the 'find:' label spaced 6 spaces from the entry
        entry_hbox = gtk.HBox(spacing=6)
        entry_hbox.pack_start(find_label, False, False)
        entry_hbox.pack_start(self._find_entry, True, True)
        
        # Toolbar item for the find entry
        entry_item = gtk.ToolItem()
        entry_item.add(entry_hbox)
        self.add(entry_item)

        # Setup the previous button
        self._find_prev = gtk.ToolButton('gtk-go-back')
        self._find_prev.set_label('Previous')
        self._find_prev.set_is_important(True)
        self._find_prev.connect('clicked', self.find_on_page)
        self._find_prev.set_tooltip_text('Find previous')
        self.add(self._find_prev)

        # Setup the forward button
        next_image = gtk.Image()
        next_image.set_from_stock('gtk-go-forward', gtk.ICON_SIZE_MENU)
        self._find_next = gtk.Button()
        self._find_next.set_image(next_image)
        self._find_next.set_image_position(gtk.POS_RIGHT)
        self._find_next.set_relief(gtk.RELIEF_NONE)
        self._find_next.set_label('Next')
        self._find_next.set_tooltip_text('Find next')
        self._find_next.connect('clicked', self.find_on_page)

        # Toolbar item for the forward button
        item = gtk.ToolItem()
        item.add(self._find_next)

        self.add(item)

        # Setup the match case button
        self._match_case = gtk.ToggleToolButton('Match Case')
        self._match_case.set_icon_name('tools-check-spelling')
        self._match_case.set_label('Match Case')
        self._match_case.set_tooltip_text('Make find case sensitive')
        self._match_case.connect('toggled', self._match_case_toggled)
        self._match_case.set_is_important(True)
        self.add(self._match_case)

        # Setup the highlight match button
        self._highlight_match = gtk.ToggleToolButton('Highlight Matches')
        self._highlight_match.set_icon_name('edit-select-all')
        self._highlight_match.set_label('Highlight Matches')
        self._highlight_match.set_tooltip_text('Highlight find results')
        self._highlight_match.set_active(True)
        self._highlight_match.connect('toggled', self._highlight_toggled)
        self._highlight_match.set_is_important(True)
        self.add(self._highlight_match)

        # Setup the dynamic find button
        self._dynamic_find = gtk.ToggleToolButton('Dynamic Find')
        self._dynamic_find.set_icon_name('insert-text')
        self._dynamic_find.set_label('Dynamic Find')
        self._dynamic_find.set_tooltip_text('Find as you type')
        self._dynamic_find.set_active(True)
        self._dynamic_find.set_is_important(True)
        self.add(self._dynamic_find)

        # Setup the wrap button
        self._wrap_find = gtk.ToggleToolButton('Wrap')
        self._wrap_find.set_icon_name('document-revert')
        self._wrap_find.set_label('Wrap')
        self._wrap_find.set_tooltip_text(
                'Wrap find to top when it reaches the bottom'
                )
        self._wrap_find.set_active(True)
        self._wrap_find.set_is_important(True)
        self.add(self._wrap_find)

        # Put a space between the last button and the close button
        space_item = gtk.ToolItem()
        space_item.set_expand(True)
        self.add(space_item)

        # Setup the close button
        close_button = gtk.ToolButton('')
        close_button.set_icon_name('window-close')
        close_button.set_tooltip_text('Close find bar')
        close_button.connect('clicked', self.toggle_visibility)
        self.add(close_button)

    def get_match_case(self):
        """ get_match_case() -> Returns a boolean indicating the state of the
        match case toggle button.

        """

        return self._match_case.get_active()

    def get_highlight(self):
        """ get_highlight() -> Returns a boolean indicating the state of the
        highlight match toggle button.

        """

        return self._highlight_match.get_active()

    def get_dynamic(self):
        """ get_dynamic() -> Returns a boolean indicating the state of the
        dynamic match toggle button.

        """

        return self._dynamic_find.get_active()

    def get_wrap(self):
        """ get_wrap() -> Returns a boolean indicating the state of the wrap
        toggle button.

        """
        
        return self._wrap_find.get_active()

    def get_text(self):
        """ get_text -> Returns the text in the find entry.

        """

        return self._find_entry.get_text()
        
    def set_stop(self):
        """ set_stop -> Set the find entry icon to 'gtk-stop.'

        """

        self._find_entry.set_icon_from_icon_name(0, 'gtk-stop') 

    def set_find(self):
        """ set_stop -> Set the find entry icon to 'gtk-find.'

        """

        self._find_entry.set_icon_from_icon_name(0, 'gtk-find') 

    def set_text(self, text):
        """ set_text(text) -> Set the find entry text to text.

        """

        self._find_entry.set_text(text)

    def is_visible(self):
        """ is_visible() -> Returns a Boolean indicating the visibility
        if the toolbar.
        
        """

        return self.get_property('visible')

    def toggle_visibility(self, close_button=None, find_text=None):
        """ toggle_visibility(close_button=None, find_text=None) -> Toggle 
        the visibility of the findbar, and set the find text. 
        
        """

        # Set the find text to find_text if set.
        if find_text:
            self._find_entry.set_text(find_text)

        # Set the focus to the find entry if it is visible.
        if self.get_property('visible') and not self._find_entry.has_focus():
            if not close_button:
                self._find_entry.grab_focus()
                return

        # Make it not/show when show_all is called
        self.set_no_show_all(not self.get_no_show_all())

        # Set it in/visible
        self.set_property('visible', not \
                self.get_property('visible'))

        if self.get_property('visible'):
            self.show_all()

            # Set input focus to the find entry if it was toggled visible
            self._find_entry.grab_focus()

    def _find_icon_release(self, find_entry, position, event):
        """ _find_icon_release(find_entry, position, event) -> Called when the
        mouse button is released after clicking one of the icons in the find
        entry. 
        
        """

        if position == gtk.ENTRY_ICON_SECONDARY:
            # Clear the find entry if the right(secondary) icon was clicked
            find_entry.set_text('')

    def _match_case_toggled(self, match_case):
        """ _match_case_toggled(match_case) -> The inheritor should handle
        setting and un-setting the case sensitivity in the browser. 
        
        """

        if not self._dynamic_find.get_active():
            self.emit('match-case-toggled', self._match_case.get_active())

    def _highlight_toggled(self, highlight_match):
        """ _highlight_toggled(highlight_match) -> The inheritor should handle
        toggling the highlight in the browser. 
        
        """

        if not self._dynamic_find.get_active():
            self.emit('highlight-toggled', self._highlight_match.get_active())

    def find_on_page(self, widget=None):
        """ find_on_page(widget) -> Find text on the page.  Depending on what
        widget was clicked to call this function it either searches forward
        or backward on the page. 
        
        """

        # Text to search for
        find_string = self._find_entry.get_text() 

        if widget == self._find_prev:
            self.emit('find-previous', find_string)
        else:
            self.emit('find-next', find_string)

    def _find_entry_changed(self, find_entry):
        """ _find_entry_changed(find_entry) -> Called when the text in the
        find entry is changed.  Performs searching while typing if it is
        enabled. 
        
        """

        if self._dynamic_find.get_active():
            self.find_on_page()
