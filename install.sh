#!/bin/bash

# Edit these paths to suit your local environment
BIN_PATH="$HOME/bin"
PKG_PATH="$HOME/.local/lib/python3.3/site-packages"
DATA_PATH="$HOME/.share/AlbumGenerator"

#
# You probably shouldn't edit anything below this.
#
PATH=/bin:/usr/bin

PKG_NAME="album_generator"

mkdir -p "$PKG_PATH"/"$PKG_NAME"
echo "__all__ = []" > "$PKG_PATH"/"$PKG_NAME"/__init__.py
pyuic4 tools/AlbumGeneratorUI.ui > "$PKG_PATH"/"$PKG_NAME"/ui.py
cp tools/util.py tools/photo.py "$PKG_PATH"/"$PKG_NAME"/

mkdir -p "$BIN_PATH"
cat tools/AlbumGenerator.py | sed -e "s@^DATA_PATH[ ]*=.*\$@DATA_PATH = \"${DATA_PATH}\"@" > "$BIN_PATH"/AlbumGenerator
chmod +x "$BIN_PATH"/AlbumGenerator

mkdir -p "$DATA_PATH"
cp www/* "$DATA_PATH"/
pandoc README -t html5 -s -S --template=misc/html5.pandoc >"$DATA_PATH"/README.html

