#!/bin/sh

# photorename.sh
# Copyright (c) Rennie deGraaf, 2010-2018.
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

# Usage: photorename.sh [+<add>] <camera name> <photos...>
# If the optional parameter "+<add>" is provided, then that number will be 
# added to photo numbers.
# For example, "$ photorename.sh +10000 sx10 2014/*.JPG" will rename all ".JPG" 
# files in "2014/" to names like "sx10_10023.jpeg".

# author: Rennie deGraaf <rennie.degraaf@gmail.com>
# version: VERSION
# date: DATE


PATH=/bin:/usr/bin

add=0
if [ 1 -lt $# ]
then
    if [ 2 -lt $# ] && [[ $1 == +* ]]
    then
        add=${1##+}
        shift
    fi
    camera=$1
    shift
else
    echo "Usage: $0 [+<add>] <camera name> <photos...>"
    exit 1
fi

for file in "$@"
do
    dir_name=$(dirname "$file")
    file_name=$(basename "$file")
    declare -i number

    # Extract the photo's number
    # Make sure to remove leading zeroes from the number, or bash will think 
    # that the number is in octal.
    if echo "$file_name" | grep -Ei '^[^_]+_([0-9]{4,5})\.jpe?g$' > /dev/null
    then
        # Canon numbering pattern or similar
        number=$(echo "$file_name" | sed -re 's/^[^_]+_0*([0-9]+)\..*$/\1/')
    elif echo "$file_name" | grep -Ei '^P10([0-9]{5})\.jpe?g$' > /dev/null
    then
        # Panasonic numbering pattern
        number=$(echo "$file_name" | sed -re 's/^P100*([0-9]+)\..*$/\1/')
    else 
        echo "Unrecognized file name pattern '" "$file" "'"
        continue
    fi

    # Add to the number if requested
    number=$((number+add))

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
