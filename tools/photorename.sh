#!/bin/sh

# photorename.sh
# Copyright Rennie deGraaf, 2009.  All rights reserved.
#
# Rename photos to encode a camera name into the file names rather than a 
# meaningless string like "IMG".  Use a ".jpeg" suffix on the resulting names.
# If any gThumb XML comment files are found for the photos being renamed, 
# rename them too.
#
# Usage: photorename.sh <camera name> <photos...>
# For example, "$ photorename sh SX10 2014/*.JPG" will rename all ".JPG" files 
# in "2014/" to names like "SX10_0023.jpeg".

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
    echo "$file_name" | egrep -i '^[^_]+_([0-9]{4})\.jpe?g$' > /dev/null
    if [ $? -ne 0 ]
    then
        echo "Unrecognized file pattern '" "$file" "'"
        continue
    fi

    # Extract the photo's number.
    number=$(echo $file_name | sed -re 's/^[^_]+_0*([0-9]+)\..*$/\1/')
    # I accidentally reset the numbering on my A80 in spring 2009.
    #number=$((number+4080))

    # Rename the photo
    new_name=$(printf "%s/%s_%04i.jpeg" "$dir_name" "$camera" $number)
    if [ -e "$new_name" ] # this check is vulnerable to races, so don't rely on it
    then
        echo "\"$new_name\" already exists; skipping $file"
    else
        mv -n "$file" "$new_name"
        chmod -x "$new_name"
    fi
    
    # If there's a gThumb XML comment file, rename it too.
    gthxml_name=$(echo "$dir_name"/.comments/"$file_name".xml)
    if [ -e "$gthxml_name" ]
    then
        new_name=$(printf "%s/.comments/%s_%04i.jpeg.xml" "$dir_name" "$camera" $number)
        if [ -e "$new_name" ] # this check is vulnerable to races, so don't rely on it
        then
            echo "\"$new_name\" already exists; skipping $file"
        else
            mv -n "$gthxml_name" "$new_name"
            chmod -x "$new_name"
        fi
    fi
done
