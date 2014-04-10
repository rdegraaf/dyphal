#!/bin/bash

PATH=/bin:/usr/bin

BIN_PATH="$HOME/bin"
PKG_PATH="$HOME/.local/lib/python3.3/site-packages"
DATA_PATH="$HOME/.share/AlbumGenerator"

PKG_NAME="album_generator"

mkdir -p "$PKG_PATH"/"$PKG_NAME"
echo "__all__ = []" > "$PKG_PATH"/"$PKG_NAME"/__init__.py
pyuic4 tools/AlbumGeneratorUI.ui > "$PKG_PATH"/"$PKG_NAME"/ui.py
cp tools/util.py "$PKG_PATH"/"$PKG_NAME"/

mkdir -p "$BIN_PATH"
cat tools/AlbumGenerator.py | sed -e "s@^DATA_PATH[ ]*=.*\$@DATA_PATH = \"${DATA_PATH}\"@" > "$BIN_PATH"/AlbumGenerator
chmod +x "$BIN_PATH"/AlbumGenerator

mkdir -p "$DATA_PATH"
cp www/* "$DATA_PATH"/

