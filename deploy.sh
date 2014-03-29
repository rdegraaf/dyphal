#!/bin/sh

PATH=/bin:/usr/bin

WWWROOT=~/www/misc/photo_album/

umask 0022
mkdir -p $WWWROOT
cp --no-preserve=mode www/* "$WWWROOT"
cp -r --no-preserve=mode test/ "$WWWROOT"

discount-mkd2html README
cp --no-preserve=mode README.html "$WWWROOT"

# TODO: move into the test directory
