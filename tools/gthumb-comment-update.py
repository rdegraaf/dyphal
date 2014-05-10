#!/usr/bin/python3.3

import argparse
import os
import subprocess
import json
import os.path
import xml.etree.ElementTree
import gzip
import datetime
import sys

import pytz


# TODO: support --camera-timezone=Unknown; set UTC offset to -00:00 rather than +00:00.

# Time: set XMP:DateTimeOriginal, IPTC:DateCreated/IPTC:TimeCreated, XML
# If -z was specified, use the Exif time and ignore all others.
# Otherwise, use the following order: XMP, IPTC, XML, Exif

# If gThumb3 XML is found, preserve all unrecognized elements.  
# If gThumb2 XML is found, convert it to gThumb3.
# If no gThumb XML is found, do not output gThumb XML.


BG_TIMEOUT = 5

class FileDescriptor(object):
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()
    def __init__(self, file_name, flags):
        self._fd = os.open(file_name, flags)
    def getFD(self):
        return self._fd
    def close(self):
        os.close(self._fd)
        self._fd = None


def validate_timezone(tz):
    if tz not in pytz.all_timezones:
        raise argparse.ArgumentTypeError("%s is not a recognized time zone" % (tz))
    return tz


def parse_exif_time(timestr, timezone):
    # XMP and IPTC dates look like this: 2011:07:05 09:15:59-07:00
    # datetime.datetime.strptime can't handle a ':' in UTC offsets.
    # And dateutil.parser.parse can't handle ':' as a field separator in dates.
    if 6 <= len(timestr) and (('+' == timestr[-6]) or ('-' == timestr[-6])):
        return datetime.datetime.strptime(timestr[:-3] + timestr[-2:], "%Y:%m:%d %H:%M:%S%z")
    else:
        return pytz.timezone(timezone).localize(datetime.datetime.strptime(timestr, 
                                                                           "%Y:%m:%d %H:%M:%S"))

def print_exif_time(timeobj):
    timestr = datetime.datetime.strftime(timeobj, "%Y:%m:%d %H:%M:%S")
    if None is timeobj.tzinfo:
        timestr += "+00:00"
    else:
        tzstr = datetime.datetime.strftime(timeobj, "%z")
        timestr += tzstr[:-2] + ':' + tzstr[-2:]
    return timestr


def convert_gthxml2(obj):
    description = obj.find("./Note").text
    location = obj.find("./Place").text
    timeobj = pytz.timezone("UTC").localize(datetime.datetime.fromtimestamp(int(obj.find("./Time")
                                                                                            .text)))

    root = xml.etree.ElementTree.Element("comment")
    root.set("version", "3.0")
    root.append(xml.etree.ElementTree.Element("caption"))
    noteElmt = xml.etree.ElementTree.Element("note")
    noteElmt.text = description
    root.append(noteElmt)
    placeElmt = xml.etree.ElementTree.Element("place")
    placeElmt.text = location
    root.append(placeElmt)
    timeElmt = xml.etree.ElementTree.Element("time")
    timeElmt.set("value", print_exif_time(timeobj))
    root.append(timeElmt)
    root.append(xml.etree.ElementTree.Element("categories"))

    #xml.etree.ElementTree.dump(root)
    return root

def extract_localize_time(embedded_props, xml_props, camera_timezone, timezone):
    # Localize the EXIF time; ignore all others
    if "EXIF:DateTimeOriginal" in embedded_props:
        return pytz.timezone(camera_timezone).localize(datetime.datetime.strptime(
                embedded_props["EXIF:DateTimeOriginal"], "%Y:%m:%d %H:%M:%S")).astimezone(
                pytz.timezone(timezone))
    else:
        return None


def extract_time(embedded_props, xml_props):
    # Look for a localized time.
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

def extract_location(embedded_props, xml_props):
    # Extract the location
    if "XMP:Location" in embedded_props:
        return embedded_props["XMP:Location"]
    elif "IPTC:ContentLocationName" in embedded_props:
        return embedded_props["IPTC:ContentLocationName"]
    elif (None is not xml_props) and (None is not xml_props.find("place")):
        return xml_props.find("place").text
    else:
        return None

def extract_description(embedded_props, xml_props):
    # Extract the description
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


def open_xml_comments(file_name):
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


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Update gThumb photo metadata")
    parser.add_argument("-p", "--print", required=False, action="store_true", dest="print_", 
                        help="Print comment data; don't update files")
    parser.add_argument("-z", "--timezone", metavar="<time zone>", type=validate_timezone, 
                        required=False, help="Time zone where the photos were taken")
    parser.add_argument("-c", "--camera-timezone", metavar="<time zone>", type=validate_timezone, 
                        required=False, default="UTC", help="Time zone for times set by the camera")
    parser.add_argument("file_names", metavar="photo", type=str, nargs="+", 
                        help="Photo whose metadata is to be updated")
    args = parser.parse_args()
    assert(0 != len(args.file_names))

    # Process files
    for file_name in args.file_names:
        try:
            photo_fd = None
            xml_fd = None
            # TODO: handle the exceptions thrown if opening the file fails.
            photo_fd = os.open(file_name, os.O_RDONLY)
            photo_path = "/proc/%d/fd/%d" % (os.getpid(), photo_fd)
            properties_text = subprocess.check_output(
                                            ["exiftool", "-json", "-a", "-G", "-All", photo_path], 
                                            timeout=BG_TIMEOUT, universal_newlines=True, 
                                            stderr=subprocess.STDOUT)
            embedded_props = json.loads(properties_text)[0]
            #print(embedded_props)
            # Try to read the XML comment file.  
            # It's not an error for it to be missing or unparsable.
            (xml_props, xml_path, xml_fd) = open_xml_comments(file_name)

            props = {}

            # Extract the description, location, date and time from the photo properties.
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
                # Update embedded fields
                pass
                if None is not xml_props:
                    # Update XML
                    xml_props.find("note").text = props["description"]
                    xml_props.find("place").text = props["location"]
                    xml_props.find("time").set("value", print_exif_time(props["time"]))
                    doc = xml.etree.ElementTree.ElementTree(xml_props)
                    doc.write(sys.stdout, encoding="unicode", xml_declaration=True)
                    pass

        except (FileNotFoundError):
            print("Error reading", file_name)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print("Error reading metadata for", file_name)
        finally:
            if None is not xml_fd:
                os.close(xml_fd)
            if None is not photo_fd:
                os.close(photo_fd)

if __name__ == '__main__':
    main()

