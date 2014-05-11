#!/bin/sh
# Installation script for Dyphal.

# Edit these paths to suit your local environment
BIN_PATH="$HOME/bin"
PKG_PATH="$HOME/.local/lib/python3.3/site-packages"
DATA_PATH="$HOME/.share/dyphal"

#
# You probably shouldn't edit anything below this.
#
PATH=/bin:/usr/bin

PKG_NAME="dyphal"

mkdir -p "$PKG_PATH"/"$PKG_NAME"
# Copy the header of DyphalGenerator.py into __init__.py
cat tools/DyphalGenerator.py | sed -e '/^#!.*/d' -e '/^import/,$d' >"$PKG_PATH"/"$PKG_NAME"/__init__.py
cp tools/ui-header.py "$PKG_PATH"/"$PKG_NAME"/ui.py
pyuic4 tools/DyphalGenerator.ui >>"$PKG_PATH"/"$PKG_NAME"/ui.py
cp tools/util.py tools/photo.py "$PKG_PATH"/"$PKG_NAME"/

mkdir -p "$BIN_PATH"
cat tools/DyphalGenerator.py | sed -e "s@^DATA_PATH[ ]*=.*\$@DATA_PATH = \"${DATA_PATH}\"@" > "$BIN_PATH"/DyphalGenerator
chmod +x "$BIN_PATH"/DyphalGenerator

mkdir -p "$DATA_PATH"
cp www/* "$DATA_PATH"/
pandoc README -t html5 -s -S --template=misc/html5.pandoc >"$DATA_PATH"/README.html

cp tools/gthumb-comment-update.py "$BIN_PATH"/gthumb-comment-update
chmod +x "$BIN_PATH"/gthumb-comment-update

cp tools/photorename.sh "$BIN_PATH"/photorename.sh
chmod +x "$BIN_PATH"/photorename.sh

