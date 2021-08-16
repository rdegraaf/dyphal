#!/bin/bash
# Execute test cases for Dyphal.

PATH=/bin:/usr/bin
export PYTHONPATH=$PYTHONPATH:$PWD/tools/

cd test

if ! python3 test_DyphalGenerator_Album_load.py $1
then
    exit
fi

if ! python3 test_DyphalGenerator_Album_save.py $1
then
    exit
fi

if ! python3 test-DyphalGenerator-LinuxSafeFile.py $1
then
    exit
fi
