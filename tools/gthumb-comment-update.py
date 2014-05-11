#!/usr/bin/python3.3

"""Photo timestamp localizer and metatada maintenance tool.
Copyright (c) Rennie deGraaf, 2010-2014.

gthumb-comment-update translates various formats of photo metadata that 
gThumb has used over the years into the format expected by 
DyphalGenerator and ensures that all metadata fields that hold the same 
information are consistent with each other.  It also allows time zones 
to be set on photo timestamps.

gthumb-comment-update requires Python 3.3 or later, only runs on Linux, 
and requires that the command 'exiftool' is available in the current 
path.

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
__author__ = "Rennie deGraaf <rennie.degraaf@gmail.com>"
__version__ = "3.0-beta1"
__credits__ = "Rennie deGraaf"
__date__ = "2014-05-10"

import argparse
import os
import subprocess
import json
import os.path
import xml.etree.ElementTree
import gzip
import datetime
import tempfile
import tarfile

import pytz


# Time: set XMP:DateTimeOriginal, IPTC:DateCreated/IPTC:TimeCreated, XML
# If -z was specified, use the Exif time and ignore all others.
# Otherwise, use the following order: XMP, IPTC, XML, Exif

# If gThumb3 XML is found, preserve all unrecognized elements.  
# If gThumb2 XML is found, convert it to gThumb3.
# If no gThumb XML is found, do not output gThumb XML.


BG_TIMEOUT = 5

def validate_timezone(tz):
    """Ensure that tz is a recognized time zone."""
    if tz not in pytz.all_timezones:
        raise argparse.ArgumentTypeError("%s is not a recognized time zone" % (tz))
    return tz


def parse_exif_time(timestr, timezone):
    """Parse a timestamp from the ideosyncratic format used in photo 
    metadata to a datetime object, using the supplied timezone if none 
    is present in the timestamp."""
    # XMP and IPTC dates look like this: 2011:07:05 09:15:59-07:00
    # datetime.datetime.strptime can't handle a ':' in UTC offsets.
    # And dateutil.parser.parse can't handle ':' as a field separator in dates.
    if 6 <= len(timestr) and (('+' == timestr[-6]) or ('-' == timestr[-6])):
        return datetime.datetime.strptime(timestr[:-3] + timestr[-2:], "%Y:%m:%d %H:%M:%S%z")
    else:
        return pytz.timezone(timezone).localize(datetime.datetime.strptime(timestr, 
                                                                           "%Y:%m:%d %H:%M:%S"))

def print_exif_time(timeobj):
    """Serialize a datetime object to the ideosyncratic format used in 
    photo metadata."""
    timestr = datetime.datetime.strftime(timeobj, "%Y:%m:%d %H:%M:%S")
    if None is timeobj.tzinfo:
        timestr += "+00:00"
    else:
        tzstr = datetime.datetime.strftime(timeobj, "%z")
        timestr += tzstr[:-2] + ':' + tzstr[-2:]
    return timestr


def convert_gthxml2(obj):
    """Translate a gThumb 2 XML comment file to the gThumb 3 format."""
    description = obj.find("./Note").text
    location = obj.find("./Place").text
    timeobj = pytz.timezone("UTC").localize(datetime.datetime.fromtimestamp(int(obj.find("./Time")
                                                                                            .text)))

    root = xml.etree.ElementTree.Element("comment")
    root.set("version", "3.0")
    root.append(xml.etree.ElementTree.Element("caption"))
    note_elmt = xml.etree.ElementTree.Element("note")
    note_elmt.text = description
    root.append(note_elmt)
    place_elmt = xml.etree.ElementTree.Element("place")
    place_elmt.text = location
    root.append(place_elmt)
    time_elmt = xml.etree.ElementTree.Element("time")
    time_elmt.set("value", print_exif_time(timeobj))
    root.append(time_elmt)
    root.append(xml.etree.ElementTree.Element("categories"))

    #xml.etree.ElementTree.dump(root)
    return root


def extract_description(embedded_props, xml_props):
    """Extracts a photo description from the given embedded and XML 
    properties."""
    if "XMP:Description" in embedded_props:
        return embedded_props["XMP:Description"]
    elif "IPTC:Caption-Abstract" in embedded_props:
        return embedded_props["IPTC:Caption-Abstract"]
    elif "EXIF:UserComment" in embedded_props and 0 != len(embedded_props["EXIF:UserComment"]):
        return embedded_props["EXIF:UserComment"]
    elif (None is not xml_props) and (None is not xml_props.find("note")):
        return xml_props.find("note").text
    else:
        return None


def extract_location(embedded_props, xml_props):
    """Extracts a photo location from the given embedded and XML 
    properties."""
    if "XMP:Location" in embedded_props:
        return embedded_props["XMP:Location"]
    elif "IPTC:ContentLocationName" in embedded_props:
        return embedded_props["IPTC:ContentLocationName"]
    elif (None is not xml_props) and (None is not xml_props.find("place")):
        return xml_props.find("place").text
    else:
        return None


def extract_time(embedded_props, xml_props):
    """Extracts a localized photo timestamp from the given embedded and 
    XML properties.  If there isn't one, falls back to the EXIF time."""
    if "XMP:DateTimeOriginal" in embedded_props:
        return parse_exif_time(embedded_props["XMP:DateTimeOriginal"], "UTC")
    elif ("IPTC:DateCreated" in embedded_props) and ("IPTC:TimeCreated" in embedded_props):
        return parse_exif_time(embedded_props["IPTC:DateCreated"] + " " + 
                               embedded_props["IPTC:TimeCreated"], "UTC")
    elif (None is not xml_props) and (None is not xml_props.find("time")) and \
         (None is not xml_props.find("time").get("value")):
        return parse_exif_time(xml_props.find("time").get("value"), "UTC")
    elif "EXIF:DateTimeOriginal" in embedded_props:
        return parse_exif_time(embedded_props["EXIF:DateTimeOriginal"], "UTC")
    else:
        return None


def extract_localize_time(embedded_props, xml_props, camera_timezone, timezone):
    """Extract and localize the EXIF timestamp from a photo."""
    if "EXIF:DateTimeOriginal" in embedded_props:
        return pytz.timezone(camera_timezone).localize(datetime.datetime.strptime(
                embedded_props["EXIF:DateTimeOriginal"], "%Y:%m:%d %H:%M:%S")).astimezone(
                pytz.timezone(timezone))
    else:
        return None


def open_xml_comments(file_name):
    """Attempts to open an XML comment file for a photo.  If a gThumb 2 
    comment file is found, updates it to the gThumb 3 format.  It is 
    not an error if the XML comment file cannot be opened or parsed."""
    xml_fd = None
    try:
        xml_fd = os.open(os.path.join(os.path.dirname(file_name), ".comments", 
                                                os.path.basename(file_name) + ".xml"), os.O_RDWR)
        xml_path = "/proc/%d/fd/%d" % (os.getpid(), xml_fd)
        try:
            xml_props = xml.etree.ElementTree.parse(xml_path).getroot()
        except (xml.etree.ElementTree.ParseError):
            # Maybe it's compressed?
            with gzip.GzipFile(xml_path, mode="r") as compressed_xml:
                xml_props = xml.etree.ElementTree.fromstring(compressed_xml.read())

        if ("comment" == xml_props.tag) and ("3.0" == xml_props.get("version")):
            # gThumb 3 XML
            return (xml_props, xml_path, xml_fd)
        elif ("Comment" == xml_props.tag) and ("2.0" == xml_props.get("format")):
            # gThumb 2 XML
            return (convert_gthxml2(xml_props), xml_path, xml_fd)
    except (FileNotFoundError, OSError, AssertionError):
        if None is not xml_fd:
            os.close(xml_fd)
    return (None, None, None)


def update_photo_props(props, embedded_props, xml_props, photo_path, xml_path):
    """Writes photo comments into the photo metadata.  If an XML 
    comment file was found, updates it as well."""
    # Build an exiftool command and update xml_props.
    exiftool_cmd = ["exiftool", "-P", "-overwrite_original_in_place"]
    if None is not props["description"]:
        exiftool_cmd.append("-XMP:Description=" + props["description"])
        if "IPTC:Caption-Abstract" in embedded_props:
            exiftool_cmd.append("-IPTC:Caption-Abstract=" + props["description"])
        if "EXIF:UserComment" in embedded_props:
            exiftool_cmd.append("-EXIF:UserComment=" + props["description"])
        if None is not xml_props:
            xml_props.find("note").text = props["description"]
    if None is not props["location"]:
        exiftool_cmd.append("-XMP:Location=" + props["location"])
        if "IPTC:ContentLocationName" in embedded_props:
            exiftool_cmd.append("-IPTC:ContentLocationName=" + props["location"])
        if None is not xml_props:
            xml_props.find("place").text = props["location"]
    if None is not props["time"]:
        time_str = print_exif_time(props["time"])
        exiftool_cmd.append("-XMP:DateTimeOriginal=" + time_str)
        if "IPTC:DateCreated" in embedded_props:
            exiftool_cmd.append("-IPTC:DateCreated=" + time_str.split(" ")[0])
        if "IPTC:TimeCreated" in embedded_props:
            exiftool_cmd.append("-IPTC:DateCreated=" + time_str.split(" ")[1])
        if None is not xml_props:
            xml_props.find("time").set("value", time_str)
    exiftool_cmd.append("-XMP:XMPToolkit=")
    exiftool_cmd.append(photo_path)
    
    # Write the revised embedded properties and XML file.
    subprocess.check_call(exiftool_cmd, timeout=BG_TIMEOUT, stderr=subprocess.STDOUT)
    if None is not xml_props:
        # Update XML
        doc = xml.etree.ElementTree.ElementTree(xml_props)
        doc.write(xml_path, encoding="unicode", xml_declaration=True)


def main():
    """Main."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Update gThumb photo metadata and localize " +
                                                 "photo timestamps.")
    parser.add_argument("-p", "--print", required=False, action="store_true", dest="print_", 
                        help="Print comment data; don't update files.")
    parser.add_argument("-z", "--timezone", metavar="<time zone>", type=validate_timezone, 
                        required=False, help="Time zone where the photos were taken.")
    parser.add_argument("-c", "--camera-timezone", metavar="<time zone>", type=validate_timezone, 
                        required=False, default="UTC", help="Time zone for times set by the "
                                                "camera.  Only meaningful if --timezone is set.")
    parser.add_argument("-b", "--backup", metavar="<backup archive>", type=str, required=False,
                        help="Archive file name for photo backups.")
    parser.add_argument("file_names", metavar="photo", type=str, nargs="+", 
                        help="Photos to update.")
    args = parser.parse_args()
    assert(0 != len(args.file_names))

    backup_archive = None
    if None is not args.backup:
        backup_archive = tarfile.open(args.backup, "a")
    temp_dir = tempfile.TemporaryDirectory()

    try:
        # Process files
        for file_name in args.file_names:
            try:
                # These need to exist even if an exception is thrown so that we can clean up.
                photo_fd = None
                xml_fd = None
                
                # Open the photo file and extract any metadata present.
                photo_fd = os.open(file_name, os.O_RDONLY)
                # exiftool creates a temporary file in the same directory as the original file when 
                # writing properties.  So we need to link the file to a writable directory.
                photo_path = os.path.join(temp_dir.name, os.path.basename(file_name))
                os.symlink("/proc/%d/fd/%d" % (os.getpid(), photo_fd), photo_path)
                
                properties_text = subprocess.check_output(
                                            ["exiftool", "-json", "-a", "-G", "-All", photo_path], 
                                            timeout=BG_TIMEOUT, universal_newlines=True, 
                                            stderr=subprocess.STDOUT)
                embedded_props = json.loads(properties_text)[0]
                
                # Try to read the XML comment file.  
                # It's not an error for it to be missing or unparsable.
                (xml_props, xml_path, xml_fd) = open_xml_comments(file_name)

                # Extract the description, location, date and time from the photo properties.
                props = {}
                props["description"] = extract_description(embedded_props, xml_props)
                props["location"] = extract_location(embedded_props, xml_props)
                if None is not args.timezone:
                    props["time"] = extract_localize_time(embedded_props, xml_props, 
                                                          args.camera_timezone, args.timezone)
                else:
                    props["time"] = extract_time(embedded_props, xml_props)

                if args.print_:
                    print("**", file_name, "**")
                    print("Description:", props["description"])
                    print("Location:", props["location"])
                    print("Time:", props["time"])
                else:
                    if None is not backup_archive:
                        backup_archive.add(photo_path)
                        if None is not xml_path:
                            backup_archive.add(xml_path)
                    try:
                        update_photo_props(props, embedded_props, xml_props, photo_path, xml_path)
                    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                        print("Error saving metadata for", file_name)

            except (FileNotFoundError, OSError):
                print("Error reading", file_name)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                print("Error reading metadata for", file_name)
            finally:
                if None is not xml_fd:
                    os.close(xml_fd)
                if None is not photo_fd:
                    os.close(photo_fd)
    finally:
        temp_dir.cleanup()
        if None is not backup_archive:
            backup_archive.close()

if __name__ == '__main__':
    main()

