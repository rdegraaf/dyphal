#!/bin/sh

# Script to install the web template files to a target directory without 
# needing to run DyphalGenerator.  Intended for testing changes to the web 
# files, not for production use.

PATH=/bin:/usr/bin

if [ $# -ne 1 ]
then
    echo "Usage: $0 <www path>"
    exit 1
fi

source ./install.sh
umask 0022
cp --no-preserve=mode "$DATA_PATH"/* "$1"/

