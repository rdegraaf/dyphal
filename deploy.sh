#!/bin/sh

PATH=/bin:/usr/bin

WWWROOT=~/www/misc/photo_album/

umask 0022
mkdir -p $WWWROOT
for f in www/* test/*
do
	cp --no-preserve=mode "$f" "$WWWROOT"
done

