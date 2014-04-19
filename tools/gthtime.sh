#!/bin/bash

# gthtime.sh
# Copyright Rennie deGraaf, 2010-2013.  All rights reserved.
#
# GThumb does not provide an option to adjust the time zone on EXIF dates when
# saving comment files.  This script manipulates the comment file to adjust 
# the times in GThumb comment files from a UTC to a given time zone.

# Usage: ./gthtime.sh <TIMEZONE> <pictures> ...
# Supported time zones:
#   PST:  Pacific Standard Time (UTC-8)
#   PDT:  Pacific Daylight Savings Time (UTC-7)
#   MST:  Mountain Standard Time  (UTC-7)
#   MDT:  Mountain Daylight Savings Time (UTC-6)
#   ADT:  Atlantic Daylight Savings Time (UTC-3)

PATH=/bin:/usr/bin

PST_tz="UTC+08:00"
PDT_tz="UTC+07:00"
MST_tz="UTC+07:00"
MDT_tz="UTC+06:00"
ADT_tz="UTC+03:00"

if [ $# -lt 2 ]
then
    echo "Usage: ./gthtime.sh <TIMEZONE> <pictures> ..."
    exit 1
fi

eval tz=\$${1}_tz
if [ -z $tz ]
then
    echo "Error: unrecognized time zone.  Please use one of the time zones "
    echo "listed in gthtime.sh, or add a new one."
    exit 1
fi

tarfile="gthtime-backup.tar"
if [ -r "$tarfile" ]
then
    echo -n "Warning: backup file $tarfile already exists.  Append to it? (y/n) "
    read str
    if [ "$str" != "y" ]
    then
        exit 1
    fi
fi

for (( i=2 ; i <= $# ; i++ ))
do
    eval filepath=\${$i}
    file=${filepath##*/}
    dir=${filepath%/*}
    if [ "$dir" == "$filepath" ]
    then
        dir="."
    fi

    echo -n "$filepath..."

    commentfile=${dir}/.comments/${file}.xml
    if [ ! -w "$commentfile" ]
    then
        echo "Error opening comment file for image $filepath"
        exit 1
    fi

    if [ -w "$tarfile" ]
    then
        tar -uf "$tarfile" "$filepath" "$commentfile"
    else
        tar -cf "$tarfile" "$filepath" "$commentfile"
    fi
    if [ $? -ne 0 ]
    then
        echo "Error backing up files $filepath, $commentfile to $tarfile"
        exit 1
    fi

    ts_orig="$(exiftool -EXIF:DateTimeOriginal "$filepath" | sed -e 's/.*: //' -e 's/:/-/' -e 's/:/-/') UTC"
    if [ -z "$ts_orig" ]
    then
        echo "Error: cannot retrieve timestamp for $filepath"
        exit 1
    fi

    ts_new="$(TZ="$tz" date -d "$ts_orig" +"%Y:%m:%d %H:%M:%S%:z")"

    # fix the IPTC tags in the photo
    replace_args=("-XMP-exif:DateTimeOriginal=$ts_new")
    if [ $(exiftool -IPTC:DateCreated "$filepath" | wc -l) == 1 ]
    then
        replace_args+=("-IPTC:DateCreated=$(echo $ts_new | cut -f 1 -d ' ')")
        replace_args+=("-IPTC:TimeCreated=$(echo $ts_new | cut -f 2 -d ' ')")
    fi
    exiftool -P -overwrite_original_in_place -XMP:XMPToolkit= "${replace_args[@]}" "$filepath"

    # fix the comment file
    cat "$commentfile" | egrep '<comment version="3\.0">' >/dev/null
    if [ $? -eq 0 ]
    then
        # gThumb 3 format
        tmpfile=`mktemp -t || exit 1`
        cat "$commentfile" | sed -re "s/<time value=\"[0-9: ]+\"\/>/<time value=\"$ts_new\"\/>/" > "$tmpfile"
        mv "$tmpfile" "$commentfile"        
    else
        zcat "$commentfile" 2>/dev/null | egrep '<Comment format="2\.0">' >/dev/null
        if [ $? -eq 0 ]
        then
            # gThumb 2 format
            echo "Error: gthumb 2 comment files are not supported."
        fi
    fi

done

echo "Processed $(($#-1)) files"
echo "Backup is $tarfile"
