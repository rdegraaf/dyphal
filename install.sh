#!/bin/bash

PATH=/bin:/usr/bin

BIN_PATH="$HOME/bin"
PKG_PATH="$HOME/.lib/python3/"
DATA_PATH="$HOME/.share/AlbumGenerator"

PKG_NAME="AlbumGenerator"

mkdir -p "$PKG_PATH"/"$PKG_NAME"
touch "$PKG_PATH"/"$PKG_NAME"/__init__.py
pyuic4 tools/AlbumGeneratorUI.ui > "$PKG_PATH"/"$PKG_NAME"/ui.py

mkdir -p "$BIN_PATH"
cat tools/AlbumGenerator.py | sed -e "s@^PKG_PATH[ ]*=.*\$@PKG_PATH = \"${PKG_PATH}\"@" -e "s@^DATA_PATH[ ]*=.*\$@DATA_PATH = \"${DATA_PATH}\"@" > "$BIN_PATH"/AlbumGenerator
chmod +x "$BIN_PATH"/AlbumGenerator

mkdir -p "$DATA_PATH"
cp www/* "$DATA_PATH"/

