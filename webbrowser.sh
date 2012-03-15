#!/bin/bash
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

VERSION=0.0.18
CONFIG_PATH=$HOME/.config/webbrowser
DOC_PATH=/usr/share/doc/webbrowser-$VERSION/defaults
BROWSER_PATH=/usr/lib/webbrowser
PYTHON=$(which python2)

if [[ ! -d $CONFIG_PATH ]]
then
    mkdir -p $CONFIG_PATH
    cp $DOC_PATH/{block.uri,movie.uri} $CONFIG_PATH
fi

exec $PYTHON $BROWSER_PATH/browser.py "$@"
