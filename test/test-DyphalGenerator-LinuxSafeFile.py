#!/usr/bin/env python3

"""Test cases for DyphalGenerator's album loader.
Copyright (c) Rennie deGraaf, 2005-2017.

This program is free software; you can redistribute it and/or modify it 
under the terms of the GNU General Public License as published by the 
Free Software Foundation; either version 2 of the License, or (at your 
option) version 3.

This program is distributed in the hope that it will be useful, but 
WITHOUT ANY WARRANTY; without even the implied warranty of 
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU 
General Public License for more details.

You should have received a copy of the GNU General Public License 
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
import os.path

from util import LinuxSafeFile

TEST_CASE_DIR = "test_cases/DyphalGenerator_Album_load"


def main():
    testsTotal = 0
    testsFailed = 0
    verbosity = 0
    
    

    if 0 != testsFailed:
        print("ERROR: %d of %d tests failed!" % (testsFailed, testsTotal))
        exit(1)

if __name__ == '__main__':
    main()
