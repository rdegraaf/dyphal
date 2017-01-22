"""Utility functions and classes for DyphalGenerator.
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

import json
import copy

class ParseError(Exception):
    """Exception raised if an error was encountered while parsing a data file."""

    def __init__(self, text):
        """Initializes a ParseError."""
        super().__init__(text)

class SaveError(Exception):
    """Exception raised if an error was encountered while saving a data file."""

    def __init__(self, text):
        """Initializes a SaveError."""
        super().__init__(text)


class Album(object):
    """Methods to load and save albums."""
    VERSION_1 = 1
    VERSION_2 = 2
    CURRENT_VERSION = VERSION_2

    @staticmethod
    def load(album_file_name):
        """Load an album and return a dict containing the album data.  May 
        throw OSError if the file cannot be read or ParseError if the contents 
        are not a valid album."""
        data = None
        # This may throw OSError.
        with open(album_file_name) as album_file:
            try:
                data = json.load(album_file)
            except (json.decoder.JSONDecodeError):
                raise ParseError("Invalid file format")
        try:
            if not "albumVersion" in data.keys() or int is not type(data["albumVersion"]):
                raise ParseError("Required field 'albumVersion' is missing or has an invalid value")
            version = data["albumVersion"]
            if Album.VERSION_1 == version:
                Album._verifyAlbumV1(data)
            elif Album.VERSION_2 == version:
                # If it fails to validate as a v2 album, try to validate as a v2 web json; if that
                # succeeds, tell the user to open the correct file.
                try:
                    Album._verifyAlbumV2(data)
                except (ParseError) as ex:
                    try:
                        Album._verifyWebV2(data)
                    except:
                        raise ex
                    else:
                        raise ParseError("The selected file is a web JSON file, " \
                                         "not a Dyphal save file.")
            else:
                raise ParseError("Album version '%d' is not supported by this version of " \
                                 "DyphalGenerator" % (version))
            return data
        except (KeyError, ValueError):
            # This should not be reached; errors should be detected before exceptions are thrown.
            raise ParseError("Parse error")

    @staticmethod
    def _verifyAlbum(template, data):
        """Verify that an album matches a supported file format."""
        keys_root = data.keys()
        for key in template["string_keys_root"]:
            if key not in keys_root or str is not type(data[key]):
                raise ParseError("Required field '%s' is missing or has an invalid value" % (key))
        for key in template["string_keys_root_nonempty"]:
            if key not in keys_root or str is not type(data[key]) or 0 == len(data[key]):
                raise ParseError("Required field '%s' is missing or has an invalid value" % (key))
        for key in template["list_keys_root"]:
            if key not in keys_root or list is not type(data[key]):
                raise ParseError("Required field '%s' is missing or has an invalid value" % (key))
        for photo in data["photos"]:
            if dict is not type(photo):
                raise ParseError("Photo record %d has an invalid value" \
                                 % (data["photos"].index(photo)))
            keys_photo = photo.keys()
            for key in template["string_keys_photo"]:
                if key not in keys_photo or str is not type(photo[key]) or 0 == len(photo[key]):
                    raise ParseError("Required field '%s' in photo record %d is missing or has " \
                                     "an invalid value" % (key, data["photos"].index(photo)))
            for key in template["orientation_keys_photo"]:
                if key not in keys_photo or str is not type(photo[key]) \
                   or ("vertical" != photo[key] and "horizontal" != photo[key]):
                    raise ParseError("Required field '%s' in photo record %d is missing or has " \
                                     "an invalid value" % (key, data["photos"].index(photo)))
        for key in template["keys_properties"]:
            for prop in data[key]:
                if str is not type(prop) or 0 == len(prop):
                    raise ParseError("Required field %s contains an invalid value" % (key))
        for key in template["keys_resolution"]:
            resolution = data[key]
            if 2 != len(resolution) or int is not type(resolution[0]) \
               or int is not type(resolution[1]) or 0 >= resolution[0] or 0 >= resolution[1]:
                raise ParseError("Required field '%s' has an invalid value" % (key))

    @staticmethod
    def _verifyAlbumV1(data):
        """Verify that an document matches the v1 album file format."""
        template = {
            "string_keys_root" : ["title", "description", "footer"],
            "string_keys_root_nonempty" : ["metadataDir"],
            "list_keys_root" : ["photos", "captionFields", "propertyFields", "photoResolution"],
            "string_keys_photo" : ["name", "thumbnail", "path"],
            "orientation_keys_photo" : ["orientation"],
            "keys_properties" : ["captionFields", "propertyFields"],
            "keys_resolution" : ["photoResolution"]
        }
        Album._verifyAlbum(template, data)

    @staticmethod
    def _verifyAlbumV2(data):
        """Verify that an document matches the v2 album file format."""
        template = {
            "string_keys_root" : ["title", "description", "footer"],
            "string_keys_root_nonempty" : [],
            "list_keys_root" : ["photos", "captionFields", "propertyFields", "photoResolution"],
            "string_keys_photo" : ["path"],
            "orientation_keys_photo" : [],
            "keys_properties" : ["captionFields", "propertyFields"],
            "keys_resolution" : ["photoResolution"]
        }
        Album._verifyAlbum(template, data)

    @staticmethod
    def _verifyWebV2(data):
        """Verify that an document matches the v1 web JSON format."""
        template = {
            "string_keys_root" : ["title", "description", "footer"],
            "string_keys_root_nonempty" : ["metadataDir"],
            "list_keys_root" : ["photos"],
            "string_keys_photo" : ["name", "thumbnail"],
            "orientation_keys_photo" : ["orientation"],
            "keys_properties" : [],
            "keys_resolution" : []
        }
        Album._verifyAlbum(template, data)

    @staticmethod
    def save(album_file_name, data):
        """Save an album using the current file format."""
        data["albumVersion"] = Album.CURRENT_VERSION

        # Strip out the data that we don't need to save.
        album_data = copy.deepcopy(data)
        del album_data["metadataDir"]
        for photo in album_data["photos"]:
            del photo["name"]
            del photo["thumbnail"]
            del photo["orientation"]
        web_data = copy.deepcopy(data)
        del web_data["captionFields"]
        del web_data["propertyFields"]
        del web_data["photoResolution"]
        for photo in web_data["photos"]:
            del photo["path"]

        web_file_name = None
        if album_file_name.endswith(".dyphal"):
            web_file_name = album_file_name[:-7] + ".json"
        else:
            web_file_name = album_file_name + ".json"
        # json.dump doesn't emit a trailing newline
        try:
            with open(album_file_name, "w") as album_file:
                print(json.dumps(album_data, sort_keys=True), file=album_file)
        except (OSError) as exc:
            raise SaveError("Error writing to %s: %s" % (album_file_name, str(exc)))
        try:
            with open(web_file_name, "w") as web_file:
                print(json.dumps(web_data, sort_keys=True), file=web_file)
        except (OSError) as exc:
            raise SaveError("Error writing to %s: %s" % (web_file_name, str(exc)))

