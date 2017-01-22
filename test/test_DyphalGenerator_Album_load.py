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

from album import Album, ParseError

TEST_CASE_DIR = "test_cases/DyphalGenerator_Album_load"

def success(x):
    return True

def failure(x):
    return False

def validate_album_v1(album):
    try:
        return \
            1 == album["albumVersion"] and \
            str is type(album["title"]) and 0 != len(album["title"]) and \
            str is type(album["description"]) and 0 == len(album["description"]) and \
            str is type(album["footer"]) and 0 != len(album["footer"]) and \
            list is type(album["photos"]) and \
            dict is type(album["photos"][0]) and \
            str is type(album["photos"][0]["name"]) and 0 != len(album["photos"][0]["name"]) and \
            str is type(album["photos"][0]["thumbnail"]) and 0 != len(album["photos"][0]["thumbnail"]) and \
            "horizontal" == album["photos"][0]["orientation"] and \
            str is type(album["photos"][0]["path"]) and 0 != len(album["photos"][0]["path"]) and \
            dict is type(album["photos"][1]) and \
            str is type(album["photos"][1]["name"]) and 0 != len(album["photos"][1]["name"]) and \
            str is type(album["photos"][1]["thumbnail"]) and 0 != len(album["photos"][1]["thumbnail"]) and \
            "vertical" == album["photos"][1]["orientation"] and \
            str is type(album["photos"][1]["path"]) and 0 != len(album["photos"][1]["path"]) and \
            str is type(album["metadataDir"]) and 0 != len(album["metadataDir"]) and \
            list is type(album["captionFields"]) and 2 == len(album["captionFields"]) and \
            str is type(album["captionFields"][0]) and "Description" == album["captionFields"][0] and \
            str is type(album["captionFields"][1]) and "Location" == album["captionFields"][1] and \
            list is type(album["propertyFields"]) and 2 == len(album["propertyFields"]) and \
            "File name" == album["propertyFields"][0] and \
            "File size" == album["propertyFields"][1] and \
            list is type(album["photoResolution"]) and 2 == len(album["photoResolution"]) and \
            1024 == album["photoResolution"][0] and 768 == album["photoResolution"][1]
    except:
        return False

def validate_album_v2(album):
    try:
        return \
            2 == album["albumVersion"] and \
            str is type(album["title"]) and 0 != len(album["title"]) and \
            str is type(album["description"]) and 0 == len(album["description"]) and \
            str is type(album["footer"]) and 0 != len(album["footer"]) and \
            list is type(album["photos"]) and \
            dict is type(album["photos"][0]) and \
            str is type(album["photos"][0]["path"]) and 0 != len(album["photos"][0]["path"]) and \
            dict is type(album["photos"][1]) and \
            str is type(album["photos"][1]["path"]) and 0 != len(album["photos"][1]["path"]) and \
            list is type(album["captionFields"]) and 2 == len(album["captionFields"]) and \
            str is type(album["captionFields"][0]) and "Description" == album["captionFields"][0] and \
            str is type(album["captionFields"][1]) and "Location" == album["captionFields"][1] and \
            list is type(album["propertyFields"]) and 2 == len(album["propertyFields"]) and \
            "File name" == album["propertyFields"][0] and \
            "File size" == album["propertyFields"][1] and \
            list is type(album["photoResolution"]) and 2 == len(album["photoResolution"]) and \
            1024 == album["photoResolution"][0] and 768 == album["photoResolution"][1]
    except:
        return False

def main():
    testsTotal = 0
    testsFailed = 0
    verbosity = 0

    if 2 <= len(sys.argv):
        if "-v" == sys.argv[1]:
            verbosity = 1
        elif "-vv" == sys.argv[1]:
            verbosity = 2

    print("Testing album parsing.")

    def test_load(description, file_name, on_success, exceptions, on_failure):
        """Attempts to load an album and reports success or failure.

        Arguments:
          description: A description of the test case, at most 55 characters.
          file_name: The name of the album file to attempt to load, relative 
                  to the test case directory.
          on_success: A function to execute if loading succeeds.  The album 
                  will be passed in as an argument.  A return value of True 
                  indicates test case success; a return of False indicates 
                  failure.
          exceptions: A tuple of exceptions that indicate loading failure.
          on_failure: A function to execute if one of the exceptions in 
                  "exceptions" is caught.  The exception will be passed in as 
                  an argument.  A return value of True indicates test case 
                  success; a return of False indicates failure.
        """
        print("  Testing %s... " % (description), end="")
        nonlocal testsTotal, testsFailed
        testsTotal += 1
        try:
            album = Album.load(os.path.join(TEST_CASE_DIR, file_name))
        except exceptions as ex:
            if on_failure(ex):
                print("passed.")
                if 2 <= verbosity:
                    print(ex)
            else:
                print("FAILED!")
                testsFailed += 1
                if 1 <= verbosity:
                    print(ex)
        except (Exception) as ex:
            print("FAILED!")
            testsFailed += 1
            if 1 <= verbosity:
                print(ex)
        else:
            if on_success(album):
                print("passed.")
            else:
                print("FAILED!")
                testsFailed += 1

    test_load("non-existent file", "doesnt_exist", failure, (OSError), success)
    test_load("empty file", "empty", failure, (ParseError), success)
    test_load("invalid JSON", "bad_json", failure, (ParseError), success)
    test_load("missing version", "version_missing.json", failure, (ParseError), success)
    test_load("bad version", "version_bad.json", failure, (ParseError), success)
    test_load("unknown version", "version_unknown.json", failure, (ParseError), success)
    test_load("missing title (v1)", "v1_title_missing.json", failure, (ParseError), success)
    test_load("bad title (v1)", "v1_title_bad.json", failure, (ParseError), success)
    test_load("empty title (v1)", "v1_title_empty.json", success, (ParseError), failure)
    test_load("missing description (v1)", "v1_description_missing.json", failure, (ParseError), success)
    test_load("bad description (v1)", "v1_description_bad.json", failure, (ParseError), success)
    test_load("empty description (v1)", "v1_description_empty.json", success, (ParseError), failure)
    test_load("missing footer (v1)", "v1_footer_missing.json", failure, (ParseError), success)
    test_load("bad footer (v1)", "v1_footer_bad.json", failure, (ParseError), success)
    test_load("empty footer (v1)", "v1_footer_empty.json", success, (ParseError), failure)
    test_load("missing photos (v1)", "v1_photos_missing.json", failure, (ParseError), success)
    test_load("bad photos (v1)", "v1_photos_bad.json", failure, (ParseError), success)
    test_load("empty photos (v1)", "v1_photos_empty.json", success, (ParseError), failure)
    test_load("bad photo (v1)", "v1_photo_bad.json", failure, (ParseError), success)
    test_load("missing photo name (v1)", "v1_photo_name_missing.json", failure, (ParseError), success)
    test_load("bad photo name (v1)", "v1_photo_name_bad.json", failure, (ParseError), success)
    test_load("empty photo name (v1)", "v1_photo_name_empty.json", failure, (ParseError), success)
    test_load("missing photo thumbnail (v1)", "v1_photo_thumbnail_missing.json", failure, (ParseError), success)
    test_load("bad photo thumbnail (v1)", "v1_photo_thumbnail_bad.json", failure, (ParseError), success)
    test_load("empty photo thumbnail (v1)", "v1_photo_thumbnail_empty.json", failure, (ParseError), success)
    test_load("missing photo orientation (v1)", "v1_photo_orientation_missing.json", failure, (ParseError), success)
    test_load("bad photo orientation (v1)", "v1_photo_orientation_bad.json", failure, (ParseError), success)
    test_load("empty photo orientation (v1)", "v1_photo_orientation_empty.json", failure, (ParseError), success)
    test_load("invalid photo orientation (v1)", "v1_photo_orientation_invalid.json", failure, (ParseError), success)
    test_load("missing photo path (v1)", "v1_photo_path_missing.json", failure, (ParseError), success)
    test_load("bad photo path (v1)", "v1_photo_path_bad.json", failure, (ParseError), success)
    test_load("empty photo path (v1)", "v1_photo_path_empty.json", failure, (ParseError), success)
    test_load("missing metadataDir (v1)", "v1_metadataDir_missing.json", failure, (ParseError), success)
    test_load("bad metadataDir (v1)", "v1_metadataDir_bad.json", failure, (ParseError), success)
    test_load("empty metadataDir (v1)", "v1_metadataDir_empty.json", failure, (ParseError), success)
    test_load("missing captionFields (v1)", "v1_captionFields_missing.json", failure, (ParseError), success)
    test_load("bad captionFields (v1)", "v1_captionFields_bad.json", failure, (ParseError), success)
    test_load("empty captionFields (v1)", "v1_captionFields_empty.json", success, (ParseError), failure)
    test_load("bad caption name (v1)", "v1_caption_bad.json", failure, (ParseError), success)
    test_load("empty caption name (v1)", "v1_caption_empty.json", failure, (ParseError), success)
    test_load("missing propertyFields (v1)", "v1_propertyFields_missing.json", failure, (ParseError), success)
    test_load("bad propertyFields (v1)", "v1_propertyFields_bad.json", failure, (ParseError), success)
    test_load("empty propertyFields (v1)", "v1_propertyFields_empty.json", success, (ParseError), failure)
    test_load("bad property (v1)", "v1_property_bad.json", failure, (ParseError), success)
    test_load("empty property (v1)", "v1_property_empty.json", failure, (ParseError), success)
    test_load("missing photoResolution (v1)", "v1_photoResolution_missing.json", failure, (ParseError), success)
    test_load("bad photoResolution (v1)", "v1_photoResolution_bad.json", failure, (ParseError), success)
    test_load("empty photoResolution (v1)", "v1_photoResolution_empty.json", failure, (ParseError), success)
    test_load("invalid photoResolution (v1)", "v1_photoResolution_toomany.json", failure, (ParseError), success)
    test_load("bad photoResolution X dimension (v1)", "v1_photoResolution_X_bad.json", failure, (ParseError), success)
    test_load("invalid photoResolution X dimension (v1)", "v1_photoResolution_X_invalid.json", failure, (ParseError), success)
    test_load("bad photoResolution Y dimension (v1)", "v1_photoResolution_Y_bad.json", failure, (ParseError), success)
    test_load("invalid photoResolution Y dimension (v1)", "v1_photoResolution_Y_invalid.json", failure, (ParseError), success)
    test_load("valid album (v1)", "v1_good.json", validate_album_v1, (ParseError, OSError), failure)
    test_load("missing title (v2)", "v2_title_missing.dyphal", failure, (ParseError), success)
    test_load("bad title (v2)", "v2_title_bad.dyphal", failure, (ParseError), success)
    test_load("empty title (v2)", "v2_title_empty.dyphal", success, (ParseError), failure)
    test_load("missing description (v2)", "v2_description_missing.dyphal", failure, (ParseError), success)
    test_load("bad description (v2)", "v2_description_bad.dyphal", failure, (ParseError), success)
    test_load("empty description (v2)", "v2_description_empty.dyphal", success, (ParseError), failure)
    test_load("missing footer (v2)", "v2_footer_missing.dyphal", failure, (ParseError), success)
    test_load("bad footer (v2)", "v2_footer_bad.dyphal", failure, (ParseError), success)
    test_load("empty footer (v2)", "v2_footer_empty.dyphal", success, (ParseError), failure)
    test_load("missing photos (v2)", "v2_photos_missing.dyphal", failure, (ParseError), success)
    test_load("bad photos (v2)", "v2_photos_bad.dyphal", failure, (ParseError), success)
    test_load("empty photos (v2)", "v2_photos_empty.dyphal", success, (ParseError), failure)
    test_load("bad photo (v2)", "v2_photo_bad.dyphal", failure, (ParseError), success)
    test_load("missing photo path (v2)", "v2_photo_path_missing.dyphal", failure, (ParseError), success)
    test_load("bad photo path (v2)", "v2_photo_path_bad.dyphal", failure, (ParseError), success)
    test_load("empty photo path (v2)", "v2_photo_path_empty.dyphal", failure, (ParseError), success)
    test_load("missing captionFields (v2)", "v2_captionFields_missing.dyphal", failure, (ParseError), success)
    test_load("bad captionFields (v2)", "v2_captionFields_bad.dyphal", failure, (ParseError), success)
    test_load("empty captionFields (v2)", "v2_captionFields_empty.dyphal", success, (ParseError), failure)
    test_load("bad caption name (v2)", "v2_caption_bad.dyphal", failure, (ParseError), success)
    test_load("empty caption name (v2)", "v2_caption_empty.dyphal", failure, (ParseError), success)
    test_load("missing propertyFields (v2)", "v2_propertyFields_missing.dyphal", failure, (ParseError), success)
    test_load("bad propertyFields (v2)", "v2_propertyFields_bad.dyphal", failure, (ParseError), success)
    test_load("empty propertyFields (v2)", "v2_propertyFields_empty.dyphal", success, (ParseError), failure)
    test_load("bad property (v2)", "v2_property_bad.dyphal", failure, (ParseError), success)
    test_load("empty property (v2)", "v2_property_empty.dyphal", failure, (ParseError), success)
    test_load("missing photoResolution (v2)", "v2_photoResolution_missing.dyphal", failure, (ParseError), success)
    test_load("bad photoResolution (v2)", "v2_photoResolution_bad.dyphal", failure, (ParseError), success)
    test_load("empty photoResolution (v2)", "v2_photoResolution_empty.dyphal", failure, (ParseError), success)
    test_load("invalid photoResolution (v2)", "v2_photoResolution_toomany.dyphal", failure, (ParseError), success)
    test_load("bad photoResolution X dimension (v2)", "v2_photoResolution_X_bad.dyphal", failure, (ParseError), success)
    test_load("invalid photoResolution X dimension (v2)", "v2_photoResolution_X_invalid.dyphal", failure, (ParseError), success)
    test_load("bad photoResolution Y dimension (v2)", "v2_photoResolution_Y_bad.dyphal", failure, (ParseError), success)
    test_load("invalid photoResolution Y dimension (v2)", "v2_photoResolution_Y_invalid.dyphal", failure, (ParseError), success)
    test_load("web JSON format (v2)", "v2_web_good.json", failure, (ParseError), success)
    test_load("valid album (v2)", "v2_good.dyphal", validate_album_v2, (ParseError, OSError), failure)

    if 0 != testsFailed:
        print("ERROR: %d of %d tests failed!" % (testsFailed, testsTotal))
        exit(1)

if __name__ == '__main__':
    main()
