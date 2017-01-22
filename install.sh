#!/bin/sh
# Installation script for Dyphal.
#
# This script assumes that you have a cloned git tree.  It will fail badly 
# otherwise.

# Edit these paths to suit your local environment
BIN_PATH="$HOME/bin"
PKG_PATH=$(python3 -m site --user-site)
DATA_PATH="$HOME/.local/share/dyphal"
CONFIG_PATH="$HOME/.config/"

#
# You probably shouldn't edit anything below this.
#
PATH=/bin:/usr/bin

PKG_NAME="dyphal"

# Get the current version and commit date.
if git diff-index --quiet HEAD -- # returns 0 if no local changes
then
    # Clean; get the commit date.
    dirty=false
    date=$(git rev-list --max-count 1 --date=short --pretty=format:%cd HEAD | grep -v ^commit) 
else
    # Dirty; use today's date.
    dirty=true
    date=$(date --iso-8601)
fi
if version=$(git name-rev --name-only --tags --no-undefined HEAD -- 2>/dev/null)
then
    # On a tag.  Strip off the parent suffix.
    version=$(echo $version | sed -e 's/\^.*//')
else
    # Not on a tag.  Get the most recent tag and decorate it like "git describe --tags"
    tag=$(git for-each-ref refs/tags --merged HEAD --count 1 --sort -taggerdate --format '%(refname:strip=2)')
    count=$(git rev-list "${tag}"..HEAD --count)
    commit=$(git rev-list --max-count 1 --abbrev-commit HEAD)
    version="${tag}-${count}-g${commit}"
fi
if [ "$dirty" = "true" ]
then
    version="${version}-dirty"
fi

mkdir -p "$BIN_PATH"
cat tools/DyphalGenerator.py | sed -r \
        -e "s@(^__version__[ ]*=[ ]*).*\$@\1\"${version}\"@" \
        -e "s@(^__date__[ ]*=[ ]*).*\$@\1\"${date}\"@" \
        -e "s@(^DATA_PATH[ ]*=[ ]*).*\$@\1\"${DATA_PATH}\"@" \
        -e "s@(^CONFIG_PATH[ ]*=[ ]*).*\$@\1\"${CONFIG_PATH}\"@" \
    >"$BIN_PATH"/DyphalGenerator
chmod +x "$BIN_PATH"/DyphalGenerator

mkdir -p "$PKG_PATH"/"$PKG_NAME"
# Copy the header of DyphalGenerator.py into __init__.py.  Use the copy that we already prettied up.
cat "$BIN_PATH"/DyphalGenerator | sed \
        -e '/^#!.*/d' -e '/^import/,$d' \
    >"$PKG_PATH"/"$PKG_NAME"/__init__.py
cp tools/ui-header.py "$PKG_PATH"/"$PKG_NAME"/ui.py
pyuic4 tools/DyphalGenerator.ui >>"$PKG_PATH"/"$PKG_NAME"/ui.py
cp tools/util.py tools/photo.py tools/album.py "$PKG_PATH"/"$PKG_NAME"/

mkdir -p "$DATA_PATH"
cp www/* "$DATA_PATH"/
cat www/index.html | sed -r \
        -e "s@(^[ ]*<p>Version ).*(</p>\$)@\1${version}, ${date}\2@" \
    >"$DATA_PATH"/index.html
cat README | sed -r \
        -e "s@(^Version ).*\$@\1${version}, ${date}@" \
    | pandoc -t html5 -s -S --template=misc/html5.pandoc  \
    >"$DATA_PATH"/README.html

cat tools/gthumb-comment-update.py | sed -r \
        -e "s@(^__version__[ ]*=[ ]*).*\$@\1\"${version}\"@" \
        -e "s@(^__date__[ ]*=[ ]*).*\$@\1\"${date}\"@" \
    >"$BIN_PATH"/gthumb-comment-update
chmod +x "$BIN_PATH"/gthumb-comment-update

cat tools/photorename.sh | sed -r \
        -e "s@(^# version:[ ]*).*\$@\1\"${version}\"@" \
        -e "s@(^# date:[ ]*).*\$@\1\"${date}\"@" \
    >"$BIN_PATH"/photorename.sh
chmod +x "$BIN_PATH"/photorename.sh
