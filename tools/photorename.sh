#!/bin/sh

# photorename.sh
# Copyright (c) Rennie deGraaf, 2010-2017.
#
# Rename photos to encode a camera name into the file names rather than a 
# meaningless string like "IMG".  Use a ".jpeg" suffix on the resulting 
# names.  If any gThumb XML comment files are found for the photos being 
# renamed, rename them too.
#
# This program is free software; you can redistribute it and/or modify it 
# under the terms of the GNU General Public License as published by the 
# Free Software Foundation; either version 2 of the License, or (at your 
# option) version 3.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU 
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License 
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Usage: photorename.sh <camera name> <photos...>
# For example, "$ photorename.sh sx10 2014/*.JPG" will rename all ".JPG" files 
# in "2014/" to names like "sx10_00023.jpeg".

# author: Rennie deGraaf <rennie.degraaf@gmail.com>
# version: VERSION
# date: DATE


PATH=/bin:/usr/bin

if [ 1 -lt $# ]
then
    camera=$1
    shift
else
    echo "Usage: $0 <camera name> <photos...>"
    exit 1
fi

for file in "$@"
do
    dir_name=$(dirname "$file")
    file_name=$(basename "$file")

    # Make sure we're dealing with a file name pattern that we can handle.
    if ! echo "$file_name" | grep -Ei '^[^_]+_([0-9]{4,5})\.jpe?g$' > /dev/null
    then
        echo "Unrecognized file name pattern '" "$file" "'"
        continue
    fi

    # Extract the photo's number.
    number=$(echo "$file_name" | sed -re 's/^[^_]+_0*([0-9]+)\..*$/\1/')
    # I accidentally reset the numbering on my A80 in spring 2009.
    #number=$((number+4080))

    # Rename the photo
    new_name=$(printf "%s/%s_%05i.jpeg" "$dir_name" "$camera" "$number")
    if [ -e "$new_name" ] # this check is vulnerable to races, so don't rely on it
    then
        echo "\"$new_name\" already exists; skipping $file"
    else
        mv -n "$file" "$new_name"
        chmod u+w,u-x,g-x,o-x "$new_name"
        jhead -autorot "$new_name"
    fi

    # If there's a gThumb XML comment file, rename it too.
    gthxml_name="$dir_name"/.comments/"$file_name".xml
    if [ -e "$gthxml_name" ]
    then
        new_name=$(printf "%s/.comments/%s_%05i.jpeg.xml" "$dir_name" "$camera" "$number")
        if [ -e "$new_name" ] # this check is vulnerable to races, so don't rely on it
        then
            echo "\"$new_name\" already exists; skipping $file"
        else
            mv -n "$gthxml_name" "$new_name"
            chmod u-x,g-x,o-x "$new_name"
        fi
    fi
done
