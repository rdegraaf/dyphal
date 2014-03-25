#!/usr/bin/python3
# requires Python 3.3 or newer

# TODO: display properties for a selected photo somewhere
# TODO: window icon
# TODO: comments
# TODO: investigate replacing the combo boxes with buttons with menus
# TODO: UI to install the template

import sys
import os
import os.path
import xml.etree.ElementTree
import re
import threading
import concurrent.futures
import subprocess
import json
import tempfile
import traceback
import time
import functools
import contextlib
import math

from PyQt4 import QtCore
from PyQt4 import QtGui

import AlbumGeneratorUI


FILE_FORMAT_VERSION = 1
ALBUM_FILE = "album.json"
THUMB_WIDTH = 160
THUMB_HEIGHT = 120

# f = functools.partial(handleExceptions, some_callback)
# f(...)
def handleExceptions(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except:
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        raise

#with pushDir(self._config.outputDir):
#@contextlib.contextmanager
#def pushDir(path):
#    curDir = os.getcwd()
#    os.chdir(path)
#    try:
#        yield
#    finally:
#        os.chdir(curDir)


class PropertyError(Exception):
    def __init__(self, name, value):
        self.prop = name
        self.value = value
    def __str__(self):
        return "Property '%s' had an unexpected value: %s" % (self.prop, self.value)


class Property(object):
    def __init__(self, name, text, default=None, transform=None):
        self.name = name
        self.text = text
        self.default = default
        if None != transform:
            self.transform = transform

    @staticmethod
    def transform(value):
        return value


def transformExifTime(timestamp):
    try:
        parsedTime = time.strptime(timestamp, "%Y:%m:%d %H:%M:%S")
        return time.strftime("%Y-%m-%d %H:%M:%SZ", parsedTime)
    except ValueError as e:
        raise PropertyError("EXIF time", timestamp)


def formatDisplayTime(timestamp):
    """Convert an IPTC or XMP timestamp into something more appropriate for viewing"""
    try:
        parsedTime = None
        if re.match("^[0-9]{4}:[0-9]{2}:[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}$", timestamp):
            # IPTC and XMP timestamps are stored in the following odd format:
            #     YYYY:mm:dd HH:MM:SS[+-]HH:MM
            # strptime() can't parse these because of the colon in the time zone
            parsedTime = time.strptime(timestamp[:-3] + timestamp[-2:], "%Y:%m:%d %H:%M:%S%z")
        elif re.match("^[0-9]{4}:[0-9]{2}:[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$", timestamp):
            parsedTime = time.strptime(timestamp, "%Y:%m:%d %H:%M:%S")
        formattedTime = time.strftime("%d %B %Y, %H:%M", parsedTime)

        # Python 3.3's strftime ignores tm_gmtoff when formatting "%z", so I need to do it myself.
        timeZone = "UTC"
        if 0 > parsedTime.tm_gmtoff:
            timeZone += time.strftime("-%H%M", time.gmtime(-parsedTime.tm_gmtoff))
        elif 0 < parsedTime.tm_gmtoff:
            timeZone += time.strftime("+%H%M", time.gmtime(parsedTime.tm_gmtoff))

        return (formattedTime, timeZone)
    except (ValueError, TypeError) as e:
        raise PropertyError("Display time", timestamp)


class PhotoFile(QtGui.QListWidgetItem):
    """A photo to add to the album"""

    _recognizedProperties = [
        Property("Composite:Aperture", "Aperture", transform=lambda f : "f/"+str(f)),
        Property("Composite:DigitalZoom", "Digital zoom", default="None"),
        Property("Composite:DriveMode", "Drive mode", default="Normal"),
        Property("Composite:FlashType", "Flash type", default="None"),
        Property("Composite:FOV", "Field of view", transform=lambda s : s+"rees"),
        Property("Composite:FocalLength35efl", "Focal length"),
        Property("Composite:HyperfocalDistance", "Hyperfocal distance"),
        Property("Composite:ImageSize", "Image dimensions", transform=lambda s : s+" pixels"),
        #Property("Composite:ISO", "ISO"),
        Property("Composite:Lens35efl", "Lens"),
        Property("Composite:LensID", "Lens ID"),
        Property("Composite:LightValue", "Light value"),
        Property("Composite:ScaleFactor35efl", "Scale factor"),
        Property("Composite:ShootingMode", "Shooting mode"),
        Property("Composite:ShutterSpeed", "Exposure", transform=lambda s : s+" sec."),
        Property("EXIF:DateTimeOriginal", "Creation time", transform=transformExifTime),
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
        Property("MakerNotes:Rotation", "Rotation", transform=lambda i : str(i)+" degrees")
    ]


    def __init__(self, filepath, config):
        super().__init__("%s (%s)" % (os.path.basename(filepath), re.sub("^"+os.path.expanduser("~"), 
                                      "~", filepath)))
        self._fileName = os.path.basename(filepath)
        (name, suffix) = os.path.splitext(self._fileName)
        self._thumbName = name + ".thumbnail" + suffix
        self._jsonName = name + ".json"

        # To avoid TOCTOU when passing file names to other programs, we do the following:
        #  1. Create a temporary directory.
        #  2. Open the file.  Get its file descriptor.
        #  3. Construct the /proc/<pid>/fd/<fd> path to the file using the file descriptor.
        #  4. Create a symlink from the temporary directory to the /proc path.  The link's name is 
        #     unique but predictable; that's ok because the directory is secure.
        #  5. Pass the symlink's path to other programs.

        self._fileDescriptor = os.open(filepath, os.O_RDONLY)
        linkPath = os.path.join(config.tempDir.name, str(self._fileDescriptor)) + os.path.splitext(filepath)[1]
        # TODO: if the link already exists, prompt for a new name?
        os.symlink("/proc/%d/fd/%s" % (os.getpid(), self._fileDescriptor), linkPath)
        self._filePath = linkPath
        propertiesText = subprocess.check_output(["exiftool", "-json", "-a", "-G", "-All", self._filePath], timeout=5, universal_newlines=True, stderr=subprocess.STDOUT)
        propertiesObj = json.loads(propertiesText)[0]

        # exiftool finds way too many properties to force the user to sift through, so we extract 
        # only a hard-coded list of properties that are likely to be interesting.
        self.properties = {}
        for prop in self._recognizedProperties:
            if prop.name in propertiesObj:
                self.properties[prop.text] = prop.transform(propertiesObj[prop.name])
            elif None != prop.default:
                self.properties[prop.text] = prop.default

        # Override the file name property because exiftool saw the our generated file name
        self.properties["File name"] = os.path.basename(filepath)
        
        # Get the photo dimensions
        self._width = propertiesObj["File:ImageWidth"]
        self._height = propertiesObj["File:ImageHeight"]

        self.descriptions = {}

        # Get the display date, if one exists
        for tag in ["XMP:DateTimeOriginal", "Composite:DateTimeCreated", "EXIF:DateTimeOriginal"]:
            if tag in propertiesObj:
                (displayTime, timeZone) = formatDisplayTime(propertiesObj[tag])
                self.descriptions["Date"] = displayTime
                self.properties["Time zone"] = timeZone
                break

        # Get the location, if one exists
        for tag in ["XMP:Location", "IPTC:ContentLocationName"]:
            if tag in propertiesObj:
                self.descriptions["Location"] = propertiesObj[tag]
                break

        # Get the description, if one exists
        for tag in ["XMP:Description", "IPTC:Caption-Abstract", "EXIF:UserComment"]:
            if tag in propertiesObj:
                self.descriptions["Description"] = propertiesObj[tag]
                break

        #time.sleep(1)
        #for prop in self.properties.keys():
        #    print("%s: %s" % (prop, self.properties[prop]))
        #for prop in self.descriptions.keys():
        #    print("%s: %s" % (prop, self.descriptions[prop]))


    def close(self):
        os.remove(self._filePath)
        self._filePath = None
        os.close(self._fileDescriptor)
        self._fileDescriptor = None


    def getPath(self):
        return self._filePath
    def getWidth(self):
        return self._width
    def getHeight(self):
        return self._height

    def _rescale(self, pixels):
        aspect = self._width / self._height
        
        if pixels >= self._width * self._height:
            return (self._width, self._height)
        else:
            # Need to find the largest x,y such that x*y <= pixels and x/y == aspect.
            # w/h == aspect, so w == h*aspect.  Substutiting that for w, h*h*aspect <= pixels.
            # Rearranging for h gives h <= sqrt(pixels/aspect)
            height = math.sqrt(pixels / aspect)
            width = height * aspect
            return (int(width), int(height))


    def getAlbumJSON(self):
        props = {}
        props["name"] = self._fileName
        props["thumbnail"] = self._thumbName
        props["orientation"] = "horizontal" if self._width >= self._height else "vertical"
        return props


    def generateJSON(self, dirFD, pixels, descriptions, properties):
        (width, height) = self._rescale(pixels)
        
        data = {}
        data["photo"] = self._fileName
        data["width"] = str(width)
        data["height"] = str(height)
        data["caption"] = [self.descriptions[tag] for tag in descriptions]
        data["properties"] = dict((tag, self.properties[tag]) for tag in properties)
        #print(json.dumps(data, indent=2, sort_keys=True))

        def openFunc(path, flags):
            return os.open(path, flags, 0o666, dir_fd=dirFD)
        with open(self._jsonName, "w", opener=openFunc) as jsonFile:
            json.dump(data, jsonFile)

    def generatePhoto(self, dirFD, pixels):
        # TODO
        pass

    def generateThumbnail(self, dirFD, width, height):
        # TODO
        # See http://www.imagemagick.org/Usage/resize/
        pass


#class FileDescriptor(object):
#    def __init__(self, name, flags, mode=0o777, dir_fd=None):
#        self._fd = os.open(name, flags, mode, dir_fd=dir_fd)

#    def getFD(self):
#        return self._fd

#    def close(self):
#        os.close(self._fd)
#        self._fd = None

#    def __enter__(self):
#        return self

#    def __exit__(self, type, value, traceback):
#        self.close()


class Config(object):
    """Run-time configuration"""
    def __init__(self):
        # TODO: load configuration from a file
        self.photoDir = os.path.expanduser("~")
        self.gthumb3Dir = os.path.join(os.path.expanduser("~"), ".local/share/gthumb/catalogs")
        #self.gthumb2Dir = os.path.join(os.path.expanduser("~", ".gnome2/gthumb/collections")
        self.outputDir = os.path.expanduser("~")
        self.maxWorkers = 4 # TODO: how to get a good number for this?
        self.tempDir = tempfile.TemporaryDirectory()
        # TODO: store the window size, selected description and property fields, footer, and resolution

    def close(self):
        self.tempDir.cleanup()
        self.tempDir = None
        # TODO: save configuration back to a file

    def __enter__(self):
        return self
    def __exit__(self, type, value, traceback):
        self.close()


class PhotoAlbumUI(QtGui.QMainWindow, AlbumGeneratorUI.Ui_MainWindow):
    """Photo Album Generator UI"""
    _addPhotoSignal = QtCore.pyqtSignal(PhotoFile)
    _showErrorSignal = QtCore.pyqtSignal(str)
    _incProgressSignal = QtCore.pyqtSignal()
    _backgroundCompleteSignal = QtCore.pyqtSignal()

    def __init__(self, config):
        """Constructor"""
        super().__init__()
        self._config = config
        # TODO: need to call self._threads.shutdown() somewhere?
        self._threads = concurrent.futures.ThreadPoolExecutor(self._config.maxWorkers)
        self._backgroundTasks = None

        self.setupUi(self)
        self.progressBar.setVisible(False)
        self.cancelButton.setVisible(False)

        # Make re-style the various combo-boxes
        self._setButtonBoxStyle(self.addPhotosButton)
        self._setButtonBoxStyle(self.addDescriptionButton)
        self._setButtonBoxStyle(self.addPropertyButton)

        # Event handlers
        self.addPhotosButton.activated.connect(self._addPhotosHandler)
        self.removePhotosButton.clicked.connect(self._removePhotosHandler)
        self.photosList.itemActivated.connect(self._showPhoto)
        self._addPhotoSignal.connect(self._addPhoto)
        self._showErrorSignal.connect(self._showError)
        self._incProgressSignal.connect(self._incProgress)
        self._backgroundCompleteSignal.connect(self._backgroundComplete)
        self.showAllDescriptionsFlag.stateChanged.connect(self._updatePhotoDescriptions)
        self.showAllPropertiesFlag.stateChanged.connect(self._updatePhotoProperties)
        self.addDescriptionButton.activated.connect(self._addDescriptionHandler)
        self.removeDescriptionsButton.clicked.connect(self._removeDescriptionsHandler)
        self.addPropertyButton.activated.connect(self._addPropertyHandler)
        self.removePropertiesButton.clicked.connect(self._removePropertiesHandler)
        self.generateAlbumButton.clicked.connect(self._generateAlbum)
        self.openAlbumButton.clicked.connect(self._openAlbum)
        self.cancelButton.clicked.connect(self._cancelBackgroundTasks)


    def _setButtonBoxStyle(self, combobox):
        """Make a QComboBox items behave more like buttons"""
        # Make the first item unselectable
        model = combobox.model()
        firstIndex = model.index(0, combobox.modelColumn(), combobox.rootModelIndex())
        firstItem = model.itemFromIndex(firstIndex)
        firstItem.setSelectable(False)

        # Change the background color of items to match normal buttons.  They still lack the 3D 
        # effects.
        p = combobox.palette()
        p.setColor(QtGui.QPalette.Base, p.color(QtGui.QPalette.Button))
        p.setBrush(QtGui.QPalette.Base, p.brush(QtGui.QPalette.Button))
        combobox.setPalette(p)

        # To force a QGroupBox's title to the top left, add something like this to the QBroupBox's 
        # stylesheet: QGroupBox::title {subcontrol-position: top left;}


    def _addPhotosHandler(self, index):
        """Event handler for the addPhotos button"""
        self.addPhotosButton.setCurrentIndex(0)
        if 1 == index: 
            # Browse for photos
            filenames = QtGui.QFileDialog.getOpenFileNames(self, "Select photos", 
                                                       self._config.photoDir, 
                                                       "Images (*.jpg *.jpeg *.png *.tif *.tiff)")
            self._addPhotoFiles(filenames)
            if 0 < len(filenames):
                self._config.photoDir = os.path.dirname(filenames[len(filenames)-1])
        elif 2 == index:
            # Add a gThumb 3 catalog
            catalogFileName = QtGui.QFileDialog.getOpenFileName(self, "Select catalog", 
                                                        self._config.gthumb3Dir, "*.catalog")
            # The QT documentation says that getOpenFileName returns a null string on cancel.  But 
            # it returns an empty string here.  Maybe that's a PyQt bug?
            if "" != catalogFileName:
                tree = xml.etree.ElementTree.parse(catalogFileName)
                # Files appear in arbitrary order in a gThumb 3 catalog file.  
                # I assume that the display order is the names sorted alphabetically.
                filenames = sorted([QtCore.QUrl(elmt.attrib["uri"]).toLocalFile() 
                                    for elmt in tree.getroot().iter("file")])
                self._addPhotoFiles(filenames)
                self._config.gthumb3Dir = os.path.dirname(catalogFileName)
        else:
            print("ERROR: unknown index selected in 'Add Photos' control")


    def _addPhotoFiles(self, filenames):
        if 0 < len(filenames):
            self._backgroundInit(len(filenames))
            tasks = []
            task = None
            for name in filenames:
                task = self._threads.submit(self._bgAddPhoto, name, task)
                tasks.append(task)
            self._threads.submit(functools.partial(handleExceptions, self._bgAddPhotoComplete), tasks)
            self._backgroundStart(tasks)

    def _removePhotosHandler(self):
        """Event handler for the removePhotos button"""
        for item in self.photosList.selectedItems():
            # removeItemWidget() doesn't seem to work
            photo = self.photosList.takeItem(self.photosList.indexFromItem(item).row())
            photo.close()

        # Update the available properties list
        self.showAllPropertiesFlag.stateChanged.emit(0)
        self.showAllDescriptionsFlag.stateChanged.emit(0)


    def _addPhoto(self, photo):
        """Event handler to add photos to photosList"""
        self.photosList.addItem(photo)


    def _showPhoto(self, photo):
        """Event handler for activating entries in photosList"""
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(photo.getPath()))


    def _showError(self, err):
        """Show an error message."""
        QtGui.QMessageBox.question(self, "Error", err, QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)


    def _incProgress(self):
        """Increment the progress bar counter."""
        self.progressBar.setValue(self.progressBar.value() + 1)


    def _backgroundInit(self, steps):
        """Initialize the progress bar for a background action.
        This must occur before any background tasks can run."""
        self.generateAlbumButton.setVisible(False)
        self.progressBar.setMaximum(steps)


    def _backgroundStart(self, tasks):
        """Show the cancellation UI.
        It doesn't make sense to do this until after the background tasks are registered."""
        self._backgroundTasks = tasks
        self.progressBar.setValue(0)
        self.progressBar.setVisible(True)
        self.cancelButton.setVisible(True)


    def _backgroundComplete(self):
        """Dismiss the cancellation UI."""
        self.cancelButton.setVisible(False)
        self.progressBar.setVisible(False)
        self.generateAlbumButton.setVisible(True)


    def _bgAddPhoto(self, name, prevTask):
        """Background task to extract information from a photo and put it in the list when done"""
        photo = PhotoFile(name, self._config)
        # Wait for the previous photo to be loaded so that photos are added to the list in the 
        # correct order.
        if None != prevTask:
            concurrent.futures.wait([prevTask])
        self._addPhotoSignal.emit(photo)
        self._incProgressSignal.emit()


    def _bgAddPhotoComplete(self, tasks):
        # Wait for the addPhoto tasks to complete.
        (done, notDone) = concurrent.futures.wait(tasks)
        assert(0 == len(notDone))

        # Display any error messages
        errors = []
        for task in done:
            try:
                task.result()
            except FileNotFoundError as e:
                if "exiftool" == e.filename:
                    errors.append("Error executing 'exiftool'.  Is it installed?")
                else:
                    errors.append("Error opening photo " + e.filename)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                errors.append("Error reading metadata from photo " + name)
            except concurrent.futures.CancelledError:
                pass
            except:
                (exc_type, exc_value, exc_traceback) = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                errors.append(sys.exc_info())
        if 0 != len(errors):
            self._showErrorSignal.emit(str(len(errors)) + " errors were encountered loading files:\n" + "\n".join(errors))

        # Update the available properties list
        self.showAllPropertiesFlag.stateChanged.emit(0)
        self.showAllDescriptionsFlag.stateChanged.emit(0)
        
        # re-enable any disabled buttons
        self._backgroundCompleteSignal.emit()


    def _updatePhotoProperties(self):
        properties = {}
        count = self.photosList.count()
        for i in range(count):
            photo = self.photosList.item(i)
            for prop in photo.properties.keys():
                if prop in properties:
                    properties[prop] += 1
                else:
                    properties[prop] = 1

        # Remove everything except the list title
        listCount = self.addPropertyButton.count()
        for i in range(listCount-1, 0, -1):
            self.addPropertyButton.removeItem(i)

        # Add the new property fields to the list
        showAll = self.showAllPropertiesFlag.isChecked()
        for prop in sorted(properties.keys()):
            if showAll or count == properties[prop]:
                self.addPropertyButton.addItem(prop)


    def _updatePhotoDescriptions(self):
        descriptions = {}
        count = self.photosList.count()
        for i in range(count):
            photo = self.photosList.item(i)
            for prop in photo.descriptions.keys():
                if prop in descriptions:
                    descriptions[prop] += 1
                else:
                    descriptions[prop] = 1

        # Remove everything except the list title
        listCount = self.addDescriptionButton.count()
        for i in range(listCount-1, 0, -1):
            self.addDescriptionButton.removeItem(i)

        # Add the new description fields to the list
        showAll = self.showAllDescriptionsFlag.isChecked()
        for prop in sorted(descriptions.keys()):
            if showAll or count == descriptions[prop]:
                self.addDescriptionButton.addItem(prop)


    def _addDescriptionHandler(self, index):
        self.addDescriptionButton.setCurrentIndex(0)
        prop = self.addDescriptionButton.itemText(index)
        self.descriptionsList.addItem(prop)


    def _removeDescriptionsHandler(self):
        """Event handler for the removeDescriptions button"""
        for item in self.descriptionsList.selectedItems():
            # removeItemWidget() doesn't seem to work
            self.descriptionsList.takeItem(self.descriptionsList.indexFromItem(item).row())


    def _addPropertyHandler(self, index):
        self.addPropertyButton.setCurrentIndex(0)
        prop = self.addPropertyButton.itemText(index)
        self.propertiesList.addItem(prop)


    def _removePropertiesHandler(self):
        """Event handler for the removeProperties button"""
        for item in self.propertiesList.selectedItems():
            # removeItemWidget() doesn't seem to work
            self.propertiesList.takeItem(self.propertiesList.indexFromItem(item).row())


    def _generateAlbum(self):
        album = {}
        album["version"] = FILE_FORMAT_VERSION
        album["title"] = self.titleText.toPlainText()
        album["footer"] = self.footerText.toPlainText()
        album["description"] = ""
        album["photoResolution"] = tuple(int(s) for s in self.photoSizeButton.currentText().split("x"))
        album["descriptionFields"] = [self.descriptionsList.item(i).text() for i in range(0, self.descriptionsList.count())]
        album["propertyFields"] = [self.propertiesList.item(i).text() for i in range(0, self.propertiesList.count())]
        album["photos"] = [self.photosList.item(i).getAlbumJSON() for i in range(0, self.photosList.count())]
        #print(json.dumps(album, indent=2, sort_keys=True))

        # Get the output directory.
        # The KDE directory chooser dialog is all kinds of buggy: it doesn't expand the current 
        # directory on open, and double-clicking on a directory tries to rename it.  So I'm using 
        # the QT directory chooser instead.
        outDir = QtGui.QFileDialog.getExistingDirectory(self, "Album Directory", self._config.outputDir, QtGui.QFileDialog.ShowDirsOnly|QtGui.QFileDialog.DontUseNativeDialog)
        # Make sure to close this when no longer needed
        dirFD = os.open(outDir, os.O_RDONLY)
        
        # Create the album JSON file
        # TODO: dump this on a background thread
        # TODO: If this is done on a background thread, then we need to block all other background 
        # tasks until this one is complete, and then cancel them if the user refuses to overwrite 
        # a file.  But the tasks aren't even registered yet, so this task would need to register 
        # all the other tasks.  Maybe it makes more sense to check up front if the file exists and 
        # prompt to overwrite before launching background tasks, then fail if the file appeared.  
        # But then we'd still need to prevent the other tasks from running.
        with _openFile(ALBUM_FILE, 0o666, dirFD, overwritePrompt="'%s' already contains a photo album.  Overwrite it?" % (outDir), parentWindow=self, ) as jsonFile:
            json.dump(album, jsonFile)
        # Don't prompt for anything else; just overwrite it.
        count = self.photosList.count()
        if 0 < count:
            self._backgroundInit(3 * count)
            pixels = album["photoResolution"][0] * album["photoResolution"][1]
            descriptions = album["descriptionFields"]
            properties = album["propertyFields"]
            tasks = []
            for i in range(0, count):
                photo = self.photosList.item(i)
                tasks.append(self._threads.submit(self._bgGeneratePhotoJSON, photo, dirFD, pixels, descriptions, properties))
                tasks.append(self._threads.submit(self._bgGeneratePhoto, photo, dirFD, pixels))
                tasks.append(self._threads.submit(self._bgGenerateThumbnail, photo, dirFD, THUMB_WIDTH,  THUMB_HEIGHT))
            self._threads.submit(functools.partial(handleExceptions, self._bgGenerateAlbumComplete), tasks, dirFD)
        self._backgroundStart(tasks)

        self._config.outputDir = outDir


    def _bgGenerateAlbumComplete(self, tasks, dirFD):
        # Wait for the album generation tasks to complete.
        (done, notDone) = concurrent.futures.wait(tasks)
        assert(0 == len(notDone))
        
        # Display any error messages
        errors = []
        for task in done:
            try:
                task.result()
            except concurrent.futures.CancelledError:
                pass
            except:
                (exc_type, exc_value, exc_traceback) = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                errors.append(sys.exc_info())
        if 0 != len(errors):
            self._showErrorSignal.emit(str(len(errors)) + " errors were encountered generating the album:\n" + "\n".join(errors))

        # Re-enable any disabled buttons
        self._backgroundCompleteSignal.emit()

        # Close the directory
        os.close(dirFD)


    # In Python 3.4, I might be able to use functools.partialmethod to create a generic wrapper 
    # that calls self._incProgressSignal.emit() after an arbitrary method call.
    def _bgGeneratePhotoJSON(self, photo, dirFD, pixels, descriptions, properties):
        photo.generateJSON(dirFD, pixels, descriptions, properties)
        self._incProgressSignal.emit()
    def _bgGeneratePhoto(self, photo, dirFD, pixels):
        photo.generatePhoto(dirFD, pixels)
        self._incProgressSignal.emit()
    def _bgGenerateThumbnail(self, photo, dirFD, width, height):
        photo.generateThumbnail(dirFD, width, height)
        self._incProgressSignal.emit()


    def _openAlbum(self):
        # TODO
        pass


    def _cancelBackgroundTasks(self):
        """Attempt to cancel any pending background tasks."""
        for task in self._backgroundTasks:
            task.cancel()
        self._backgroundTasks = None
        self._backgroundComplete()
        pass


def _openFile(fileName, mode, dirFD, overwritePrompt=None, parentWindow=None):
    """Open an album JSON file relative to a directory.  If the file already exist, prompt the user 
    for permission to overwrite it."""
    def openFunc(path, flags):
        return os.open(path, flags, mode, dir_fd=dirFD)
    try:
        return open(fileName, "x", opener=openFunc)
    except FileExistsError:
        if overwritePrompt and QtGui.QMessageBox.Yes == QtGui.QMessageBox.warning(parentWindow, "Warning", overwritePrompt, QtGui.QMessageBox.Yes|QtGui.QMessageBox.No, QtGui.QMessageBox.No):
            return open(fileName, "w", opener=openFunc)
        else:
            raise


def main():
    with Config() as config:

        app = QtGui.QApplication(sys.argv)
        wnd = PhotoAlbumUI(config)

        wnd.show()

        sys.exit(app.exec_())

if __name__ == '__main__':
    main()
