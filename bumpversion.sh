#!/bin/sh

# Script to update version and date information in various files, and 
# optionally to create a new tagged version.

export PATH=/bin:/usr/bin

if [ $# -eq 0 ]
then
    version=$(git describe --long)
elif [ $# -eq 1 ]
then
    git tag -s "$1" || exit 1
    version=$(git describe)
else
    echo "Usage: $0 [<version>]"
    exit 1
fi

date=$(date -I)

# Update the version and date in DyphalGenerator.py
sed -i -e "s/^__version__ = .*$/__version__ = \"$version\"/" -e "s/^__date__ = .*$/__date__ = \"$date\"/" tools/DyphalGenerator.py

# Update the version and date in index.html
sed -i -re "s/^([ ]*<p>Version ).*(<\/p>)$/\1$version, $date\2/" www/index.html

# Update the version and date in README
sed -i -re "s/^(Version )[^ ]+, [[:digit:]]{4}-[[:digit:]]{2}-[[:digit:]]{2}$/\1$version, $date/" README

