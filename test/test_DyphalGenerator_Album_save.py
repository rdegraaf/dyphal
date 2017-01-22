#!/usr/bin/env python3

"""Test cases for DyphalGenerator's album serializer.
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
import copy
import tempfile
import os.path
import filecmp
import shutil
import functools

from album import Album, ParseError, SaveError

TEST_CASE_DIR = "test_cases/DyphalGenerator_Album_save"

def create_file(name, dir_name):
    with open(os.path.join(dir_name, name), "w") as f:
        pass

def create_file_ro(name, dir_name):
    umask = os.umask(0o333)
    f = open(os.path.join(dir_name, name), "w")
    print("foo", file=f)
    f.close()
    os.umask(umask)

def main():
    testsTotal = 0
    testsFailed = 0
    verbosity = 0

    if 2 <= len(sys.argv):
        if "-v" == sys.argv[1]:
            verbosity = 1
        elif "-vv" == sys.argv[1]:
            verbosity = 2

    print("Testing album serialization.")

    def test_save_success(description, data, save_name_album, save_name_web, compare_name_album, compare_name_web, pre_func):
        """Saves an album, compares the results against expected data, and 
        reports success or failure depending on whether they matched.

        Arguments:
          description: A description of the test case, at most 55 characters.
          data: A dictionary containing album data.
          save_name_album: The name under which to save the album, relative to 
                  a temporary directory.
          save_name_web: The name under which the web JSON will be saved, 
                  relative to a temporary directory.
          compare_name_album: The name of the canonical album file, relative to 
                  the test case directory.
          compare_name_web: The name of the canonical web JSON file, relative 
                  to the test case directory.
          pre_func: A function to execute before the album is saved.  The name 
                  of the temporary directory will be passed in as an argument.
        """
        print("  Testing %s... " % (description), end="")
        nonlocal testsTotal, testsFailed
        testsTotal += 1
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                if None is not pre_func:
                    pre_func(temp_dir)
                Album.save(os.path.join(temp_dir, save_name_album), data)
                if not filecmp.cmp(os.path.join(temp_dir, save_name_album), os.path.join(TEST_CASE_DIR, compare_name_album), shallow=False):
                    print("FAILED!")
                    testsFailed += 1
                    shutil.copy(os.path.join(temp_dir, save_name_album), "/tmp/album.dyphal")
                    if 1 <= verbosity:
                        with open(os.path.join(temp_dir, save_name_album), "r") as f:
                            for line in f.readlines():
                                print(line)
                elif not filecmp.cmp(os.path.join(temp_dir, save_name_web), os.path.join(TEST_CASE_DIR, compare_name_web), shallow=False):
                    print("FAILED!")
                    testsFailed += 1
                    if 1 <= verbosity:
                        with open(os.path.join(temp_dir, save_name_web), "r") as f:
                            for line in f.readlines():
                                print(line)
                else:
                    print("passed.")
        except (Exception) as ex:
            print("FAILED!")
            testsFailed += 1
            if 1 <= verbosity:
                print(ex)

    def test_save_failure(description, data, save_name_album, save_name_web, exceptions, pre_func):
        """Saves an album and verifies that an expected exception was thrown.
        
        Arguments:
          description: A description of the test case, at most 55 characters.
          data: A dictionary containing album data.
          save_name_album: The name under which to save the album, relative to 
                  a temporary directory.
          save_name_web: The name under which the web JSON will be saved, 
                  relative to a temporary directory.
          exceptions: A tuple of exceptions that indicate save failure.
          pre_func: A function to execute before the album is saved.  The name 
                  of the temporary directory will be passed in as an argument.
        """
        print("  Testing %s... " % (description), end="")
        nonlocal testsTotal, testsFailed
        testsTotal += 1
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                if None is not pre_func:
                    pre_func(temp_dir)
                Album.save(os.path.join(temp_dir, save_name_album), data)
        except exceptions as ex:
            print("passed.")
            if 2 <= verbosity:
                print(ex)
        except (Exception) as ex:
            print("FAILED!")
            testsFailed += 1
            if 1 <= verbosity:
                print(ex)
        else:
            print("FAILED!")
            testsFailed += 1

    template = {
        "title": "Test Album with an unnecessarily verbose title",
        "description": "This album is designed to test Dyphal.  It has photos with a mix of different caption types and date formats, a photo with an odd aspect ratio, a low-resolution photo, and a photo with a bunch of unusual characters in its name.",
        "footer": "Copyright © \"Rennie deGraaf\" 2005-2017. <script>All rights \nreserved.&lt;script&gt;",
        "photos": [
            {
                "name": "img_0357.jpg",
                "thumbnail": "thumbnails/img_0357.thumbnail.jpg",
                "orientation": "horizontal",
                "path": "%7E/Projects/PhotoAlbum/trunk/test/img_0357.jpg"
            },
            {
                "name": "img_2235.jpg",
                "thumbnail": "thumbnails/img_2235.thumbnail.jpg",
                "orientation": "vertical",
                "path": "%7E/Projects/PhotoAlbum/trunk/test/img_2235.jpg"
            }
        ],
        "metadataDir": "metadata/",
        "captionFields": [
            "Description",
            "Location"
        ],
        "propertyFields": [
            "File name",
            "File size"
        ],
        "photoResolution": [
            1024,
            768
        ]
    }

    test_save_success("save to non-existing album with no suffix", template, "album", "album.json", "album.dyphal", "album.json", None)
    test_save_success("save to non-existing album with suffix", template, "album.dyphal", "album.json", "album.dyphal", "album.json", None)
    test_save_success("save to pre-existing album", template, "album.dyphal", "album.json", "album.dyphal", "album.json", functools.partial(create_file, "album.dyphal"))
    test_save_success("save to pre-existing web json", template, "album.dyphal", "album.json", "album.dyphal", "album.json", functools.partial(create_file, "album.json"))
    test_save_failure("save to non-writable album", template, "album.dyphal", "album.json", (SaveError), functools.partial(create_file_ro, "album.dyphal"))
    test_save_failure("save to non-writable web json", template, "album.dyphal", "album.json", (SaveError), functools.partial(create_file_ro, "album.json"))

    if 0 != testsFailed:
        print("ERROR: %d of %d tests failed!" % (testsFailed, testsTotal))
        exit(1)

if __name__ == '__main__':
    main()
