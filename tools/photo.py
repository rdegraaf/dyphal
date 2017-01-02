"""Classes to represent a photo and its properties in DyphalGenerator.
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


import time
import re
import os
import subprocess
import json
import urllib.parse
import math

from PyQt4 import QtGui

from dyphal.util import RefCounted

class PropertyError(Exception):
    """Exception raised if a photo property has an unexpected value."""

    def __init__(self, name, value):
        """Initializes a PropertyError."""
        super().__init__()
        self.prop = name
        self.value = value

    def __str__(self):
        """Returns a printable message for a PropertyError."""
        return "Property '%s' had an unexpected value: %s" % (self.prop, self.value)


class Property(object):
    """A photo property."""

    def __init__(self, name, text, default=None, transform=None):
        """Initializes a property."""
        self.name = name
        self.text = text
        self.default = default
        if None is not transform:
            self.transform = transform
        else:
            self.transform = lambda x: x


def transform_exif_time(timestamp):
    """Converts an EXIF timestamp into something more appropriate for 
    viewing."""
    try:
        parsed_time = time.strptime(timestamp, "%Y:%m:%d %H:%M:%S")
        return time.strftime("%Y-%m-%d %H:%M:%SZ", parsed_time)
    except ValueError:
        raise PropertyError("EXIF time", timestamp)


def format_display_time(timestamp):
    """Convert an IPTC or XMP timestamp into something more appropriate for 
    viewing."""
    try:
        parsed_time = None
        if re.match("^[0-9]{4}:[0-9]{2}:[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}$", 
                    timestamp):
            # IPTC and XMP timestamps are stored in the following odd format:
            #     YYYY:mm:dd HH:MM:SS[+-]HH:MM
            # strptime() can't parse these because of the colon in the time zone
            parsed_time = time.strptime(timestamp[:-3] + timestamp[-2:], "%Y:%m:%d %H:%M:%S%z")
        elif re.match("^[0-9]{4}:[0-9]{2}:[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$", timestamp):
            parsed_time = time.strptime(timestamp, "%Y:%m:%d %H:%M:%S")
        formatted_time = time.strftime("%d %B %Y, %H:%M", parsed_time)

        # Python 3.3's strftime ignores tm_gmtoff when formatting "%z", so I need to do it myself.
        # Use RFC 3339 conventions.
        time_zone = "UTC"
        if None is parsed_time.tm_gmtoff:
            time_zone += "-00:00"
        elif 0 > parsed_time.tm_gmtoff:
            time_zone += time.strftime("-%H:%M", time.gmtime(-parsed_time.tm_gmtoff))
        elif 0 < parsed_time.tm_gmtoff:
            time_zone += time.strftime("+%H:%M", time.gmtime(parsed_time.tm_gmtoff))

        return (formatted_time, time_zone)
    except (ValueError, TypeError):
        raise PropertyError("Display time", timestamp)


class PhotoFile(RefCounted, QtGui.QListWidgetItem):
    """A photo to add to the album.

    Attributes:
        properties (dict): The properties that have been extracted from 
                this photo.
        captions (dict): The captions that have been extracted from 
                this photo.
        _fileFullPath (str): The path to the file.  May use "~" to 
                represent the user's home directory.  
                eg, "~/Photos/2013-04-03/img_3201a.jpg"
        _fileName (str): The name to use for this photo in the album.  
                Must be unique.  eg, "img_3201a.jpg"
        _jsonName (str): The name of the JSON file for this photo in 
                the album.
        _thumbName (str): The name of the thumbnail file for this photo 
                in the album.
        _linkPath (str): The full path to the link to this photo in the 
                album's temporary directory.
        _fileDescriptor (int): A file descriptor for the photo file.
        _width (int): The photo's width in pixels.
        _height (int): The photo's height in pixels.
        _config (Config): A reference to the global configuration object.
    """

    _recognizedProperties = [
        Property("Composite:Aperture", "Aperture", transform=lambda f: "f/"+str(f)),
        Property("Composite:DigitalZoom", "Digital zoom", default="None"),
        Property("Composite:DriveMode", "Drive mode", default="Normal"),
        Property("Composite:FlashType", "Flash type", default="None"),
        Property("Composite:FOV", "Field of view", transform=lambda s: s+"rees"),
        Property("Composite:FocalLength35efl", "Focal length"),
        Property("Composite:HyperfocalDistance", "Hyperfocal distance"),
        Property("Composite:ImageSize", "Image dimensions", transform=lambda s: s+" pixels"),
        #Property("Composite:ISO", "ISO"),
        Property("Composite:Lens35efl", "Lens"),
        Property("Composite:LensID", "Lens ID"),
        Property("Composite:LightValue", "Light value"),
        Property("Composite:ScaleFactor35efl", "Scale factor"),
        Property("Composite:ShootingMode", "Shooting mode"),
        Property("Composite:ShutterSpeed", "Exposure", transform=lambda s: str(s)+" sec."),
        Property("EXIF:DateTimeOriginal", "Creation time", transform=transform_exif_time),
        Property("EXIF:ExposureCompensation", "Exposure compensation"),
        Property("EXIF:ExposureMode", "Exposure mode"),
        Property("EXIF:Flash", "Flash"),
        Property("EXIF:FocalLength", "Focal length"),
        Property("EXIF:ISO", "ISO"),
        Property("EXIF:Make", "Camera make"),
        Property("EXIF:Model", "Camera model"),
        Property("EXIF:Orientation", "Orientation"),
        Property("File:FileSize", "File size"),
        Property("File:FileType", "File type"),
        Property("MakerNotes:MacroMode", "Macro mode"),
        Property("MakerNotes:Rotation", "Rotation", transform=lambda i: str(i)+" degrees")
    ]

    def __init__(self, filepath, fileName, config):
        """Initializes a PhotoFile.  Opens the file, links it to a 
        temporary directory, and extracts properties and captions 
        from it."""
        self._config = config
        self._fileName = fileName
        self._fileFullPath = re.sub("^"+os.path.expanduser("~"), "~", filepath)
        super().__init__("%s (%s)" % (self._fileName, self._fileFullPath))
        self._jsonName = self._fileName + ".json"
        (name, suffix) = os.path.splitext(self._fileName)
        self._thumbName = name + ".thumbnail" + suffix
        # Don't set linkPath until after the link has been created.  Otherwise, a FileExistsError 
        # due to us already having the file open somewhere else will result in us deleting the link 
        # when we try to clean up.
        self._linkPath = None
        self._fileDescriptor = None

        # To avoid TOCTOU when passing file names to other programs, we do the following:
        #  1. Create a secure temporary directory.
        #  2. Open the file.  Get its file descriptor.
        #  3. Construct the /proc/<pid>/fd/<fd> path to the file using the file descriptor.
        #  4. Create a symlink from the temporary directory to the /proc path.  The link's name is 
        #     unique but predictable; that's ok because the directory is secure.
        #  5. Pass the symlink's path to other programs.

        try:
            self._fileDescriptor = os.open(filepath, os.O_RDONLY)
            link_path = os.path.join(config.tempDir.name, self._fileName)
            os.symlink("/proc/%d/fd/%d" % (os.getpid(), self._fileDescriptor), link_path)
            self._linkPath = link_path
            # gThumb stores IPTC strings as UTF-8, but does not set CodedCharacterSet
            properties_text = subprocess.check_output(
                ["exiftool", "-charset", "iptc=UTF8", "-json", "-a", "-G", "-All", self._linkPath], 
                timeout=self._config.BG_TIMEOUT, universal_newlines=True, stderr=subprocess.STDOUT)
            properties_obj = json.loads(properties_text)[0]

            # exiftool finds way too many properties to force the user to sift through, so we 
            # extract only a hard-coded list of properties that are likely to be interesting.
            self.properties = {}
            for prop in self._recognizedProperties:
                if prop.name in properties_obj:
                    self.properties[prop.text] = prop.transform(properties_obj[prop.name])
                elif None is not prop.default:
                    self.properties[prop.text] = prop.default

            # Override the file name property because exiftool saw our generated file name
            self.properties["File name"] = os.path.basename(filepath)

            # Get the photo dimensions
            self._width = properties_obj["File:ImageWidth"]
            self._height = properties_obj["File:ImageHeight"]

            self.captions = {}

            # Get the display date, if one exists
            for tag in ["XMP:DateTimeOriginal", "Composite:DateTimeCreated", 
                        "EXIF:DateTimeOriginal"]:
                if tag in properties_obj:
                    (display_time, time_zone) = format_display_time(properties_obj[tag])
                    self.captions["Date"] = display_time
                    self.properties["Time zone"] = time_zone
                    break

            # Get the location, if one exists
            for tag in ["XMP:Location", "IPTC:ContentLocationName"]:
                if tag in properties_obj:
                    self.captions["Location"] = properties_obj[tag]
                    break

            # Get the description, if one exists
            for tag in ["XMP:Description", "IPTC:Caption-Abstract", "EXIF:UserComment"]:
                if tag in properties_obj:
                    self.captions["Description"] = properties_obj[tag]
                    break

        except:
            # If something failed, make sure to not leave any dangling resources.  Ignore any 
            # failures that this causes.
            try:
                self._dispose()
            except:
                pass
            raise

    def _dispose(self):
        """Close a photo file and unlink it from the temporary directory.
        Overrides RefCounted._dispose()."""
        try:
            if None is not self._linkPath:
                os.unlink(self._linkPath)
        except OSError:
            pass
        self._linkPath = None
        try:
            if None is not self._fileDescriptor:
                os.close(self._fileDescriptor)
        except OSError:
            pass
        self._fileDescriptor = None

    def getPath(self):
        """Return the path to the photo file."""
        return self._linkPath

    def _rescale(self, pixels):
        """Calculate the optimal width and height for the photo to keep 
        it under the given size."""
        aspect = self._width / self._height

        if pixels >= self._width * self._height:
            return (self._width, self._height)
        else:
            # Need to find the largest w,h such that w*h <= pixels and w/h == aspect.
            # w/h == aspect, so w == h*aspect.  Substutiting that for w, h*h*aspect <= pixels.
            # Rearranging for h gives h <= sqrt(pixels/aspect)
            height = math.sqrt(pixels / aspect)
            width = height * aspect
            return (int(width), int(height))

    def getAlbumJSON(self):
        """Return the information about the photo that's necessary for 
        the album JSON file."""
        props = {}
        props["name"] = urllib.parse.quote(self._fileName)
        props["thumbnail"] = urllib.parse.quote(os.path.join(self._config.THUMBNAIL_DIR, 
                                                             self._thumbName))
        props["orientation"] = "horizontal" if self._width >= self._height else "vertical"
        props["path"] = urllib.parse.quote(self._fileFullPath)
        return props

    def generateJSON(self, out_dir_name, width_base, height_base, captions, properties):
        """Generate the JSON file for the photo."""
        (width, height) = self._rescale(width_base * height_base)

        data = {}
        data["photo"] = urllib.parse.quote(os.path.join(self._config.PHOTO_DIR, self._fileName))
        data["width"] = str(width)
        data["height"] = str(height)
        data["caption"] = \
            [self.captions[tag] for tag in captions if tag in self.captions]
        data["properties"] = \
            [(tag, self.properties[tag]) for tag in properties if tag in self.properties]
        #print(json.dumps(data, indent=2, sort_keys=True))

        with open(os.path.join(out_dir_name, self._jsonName), "w") as json_file:
            json.dump(data, json_file, sort_keys=True)

    def generatePhoto(self, out_dir_name, width_base, height_base, quality):
        """Generate a scaled-down photo."""
        (width, height) = self._rescale(width_base * height_base)
        # See http://www.imagemagick.org/Usage/resize/
        subprocess.check_call(["convert", self._linkPath, "-resize", "%dx%d>" % (width, height), 
                               "-strip", "-quality", str(quality), 
                               os.path.join(out_dir_name, self._fileName)], 
                              timeout=self._config.BG_TIMEOUT)

    def generateThumbnail(self, out_dir_name, width_base, height_base, quality):
        """Generate a thumbnail for the photo."""
        # width_base and height_base assume a horizontal photo.  Swap them for a vertical.
        width, height = (width_base, height_base)
        if self._width < self._height:
            width, height = (height_base, width_base)
        # See http://www.imagemagick.org/Usage/thumbnails/
        subprocess.check_call(["convert", self._linkPath, "-thumbnail", "%dx%d^" % (width, height), 
                               "-gravity", "center", "-extent", "%dx%d" % (width, height), 
                               "-quality", str(quality), 
                               os.path.join(out_dir_name, self._thumbName)], 
                              timeout=self._config.BG_TIMEOUT)
