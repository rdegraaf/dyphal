#!/usr/bin/python3
# requires Python 3.3 or newer on Linux

# TODO: window icon
# TODO: comments
# TODO: reduce the spacing on items in the Add Caption and Add Property menus.
#     I tried to change the padding with a QMenu::item stylesheet, but this 
#     removed the hover effect.  I can't figure out how to get both.


import sys
import os
import os.path
import xml.etree.ElementTree
import re
import threading
#import concurrent.futures # Imported later so that the program will load under Python 2.7
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


PROGRAM_NAME = "Album Generator"
FILE_FORMAT_VERSION = 1
ALBUM_FILE = "album.json"
THUMB_WIDTH = 160
THUMB_HEIGHT = 120
CONFIG_FILE = os.path.expanduser("~/.config/AlbumGenerator.conf")

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
        self._fileName = os.path.basename(filepath)
        self._fileFullPath = re.sub("^"+os.path.expanduser("~"), "~", filepath)
        super().__init__("%s (%s)" % (self._fileName, self._fileFullPath))
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


    def _rescale(self, pixels):
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
        props = {}
        props["name"] = self._fileName
        props["thumbnail"] = self._thumbName
        props["orientation"] = "horizontal" if self._width >= self._height else "vertical"
        props["path"] = self._fileFullPath
        return props


    def generateJSON(self, dirFD, pixels, descriptions, properties):
        (width, height) = self._rescale(pixels)
        
        data = {}
        data["photo"] = self._fileName
        data["width"] = str(width)
        data["height"] = str(height)
        data["caption"] = [self.descriptions[tag] for tag in descriptions if tar in self.descriptions]
        data["properties"] = dict((tag, self.properties[tag]) for tag in properties if tag in self.properties)
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
        """Load the configuration file.  Populate any run-time properties not found in the file 
        with sane defaults."""
        # Load the configuration file.  Keep the handle so that we can save to the same file.
        self._file = None
        data = {}
        try:
            # Python's 'r+' mode doesn't create files if they don't already exist.
            self._file = open(CONFIG_FILE, "r+", opener=lambda path, flags: os.open(path, flags|os.O_CREAT, 0o666))
            data = json.load(self._file)
        except (FileNotFoundError, ValueError):
            # open() can fail with FileNotFoundError if a directory in the path doesn't exist.
            # json.load() can fail with ValueError if the file is empty or otherwise invalid.
            pass
        except:
            # We'll just ignore any other failures and continue without a configuration file.
            (exc_type, exc_value, exc_traceback) = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)

        # Used during operation and stored in the configuration file
        self.photoDir = data["photoDir"] if "photoDir" in data else os.path.expanduser("~")
        self.gthumb3Dir = data["gthumb3Dir"] if "gthumb3Dir" in data else os.path.join(os.path.expanduser("~"), ".local/share/gthumb/catalogs")
        #self.gthumb2Dir = data["gthumb2Dir"] if "gthumb2Dir" in data else os.path.join(os.path.expanduser("~"), ".gnome2/gthumb/collections")
        self.outputDir = data["outputDir"] if "outputDir" in data else os.path.expanduser("~")
        
        # Used only at startup and stored in the configuration file
        self.dimensions = data["dimensions"] if "dimensions" in data else None
        self.uiData = data["uiData"] if "uiData" in data else None
        
        # Not stored in the configuration file
        self.maxWorkers = 4 # TODO: how to get a good number for this?
        self.tempDir = tempfile.TemporaryDirectory()


    def save(self):
        """Save the current state to the configuration file"""
        # If we couldn't open or create the config file, don't bother saving.
        if None != self._file:
            data = {}
            data["photoDir"] = self.photoDir
            data["gthumb3Dir"] = self.gthumb3Dir
            data["outputDir"] = self.outputDir
            data["dimensions"] = self.dimensions
            data["uiData"] = self.uiData

            self._file.seek(0)
            self._file.truncate(0)
            json.dump(data, self._file)
            self._file.flush()


    def close(self):
        """Close the configuration file and tear down any global runtime state."""
        self.tempDir.cleanup()
        self.tempDir = None
        self._file.close()
        self._file = None
        # TODO: save configuration back to a file

    def __enter__(self):
        return self
    def __exit__(self, type, value, traceback):
        self.close()


class ListKeyFilter(QtCore.QObject):
    delKeyPressed = QtCore.pyqtSignal()
    escKeyPressed = QtCore.pyqtSignal()
    
    def eventFilter(self, obj, event):
        if QtCore.QEvent.KeyPress == event.type():
            if QtCore.Qt.Key_Delete == event.key():
                self.delKeyPressed.emit()
                return True
            elif QtCore.Qt.Key_Escape == event.key():
                self.escKeyPressed.emit()
                return True
        return False


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
        self._threads = concurrent.futures.ThreadPoolExecutor(self._config.maxWorkers)
        self._backgroundTasks = None

        self.setupUi(self)
        if None != self._config.dimensions:
            self.resize(*self._config.dimensions)
        if None != self._config.uiData:
            self._restoreUIData(self._config.uiData)
        self.progressBar.setVisible(False)
        self.cancelButton.setVisible(False)

        # Set up the menu for the "Add Photos" button
        self._addPhotosButtonMenu = QtGui.QMenu(self.addPhotosButton)
        self._addPhotosFiles = QtGui.QAction("Add Files...", self._addPhotosButtonMenu)
        self._addPhotosGthumb3 = QtGui.QAction("Add a gThumb 3 Catalog...", self._addPhotosButtonMenu)
        self._addPhotosButtonMenu.addAction(self._addPhotosFiles)
        self._addPhotosButtonMenu.addAction(self._addPhotosGthumb3)
        self.addPhotosButton.setMenu(self._addPhotosButtonMenu)

        # Set up the menu for the "Add Caption" button
        self._addCaptionButtonMenu = QtGui.QMenu(self.addCaptionButton)
        self.addCaptionButton.setMenu(self._addCaptionButtonMenu)

        # Set up the menu for the "Add Property" button
        self._addPropertyButtonMenu = QtGui.QMenu(self.addPropertyButton)
        self.addPropertyButton.setMenu(self._addPropertyButtonMenu)

        # Listen for keyboard events in photosList, descriptionsList, and propertiesList
        self._photosListFilter = ListKeyFilter()
        self.photosList.installEventFilter(self._photosListFilter)
        self._descriptionsListFilter = ListKeyFilter()
        self.descriptionsList.installEventFilter(self._descriptionsListFilter)
        self._propertiesListFilter = ListKeyFilter()
        self.propertiesList.installEventFilter(self._propertiesListFilter)

        # Event handlers
        self._addPhotosFiles.triggered.connect(self._addPhotosHandler)
        self._addPhotosGthumb3.triggered.connect(self._addPhotosHandler)
        self.removePhotosButton.clicked.connect(self._removePhotosHandler)
        self.photosList.itemSelectionChanged.connect(self._showProperties)
        self.photosList.itemActivated.connect(self._showPhoto)
        self._addPhotoSignal.connect(self._addPhoto)
        self._showErrorSignal.connect(self._showError)
        self._incProgressSignal.connect(self._incProgress)
        self._backgroundCompleteSignal.connect(self._backgroundComplete)
        self.showAllDescriptionsFlag.stateChanged.connect(self._updatePhotoDescriptions)
        self.showAllPropertiesFlag.stateChanged.connect(self._updatePhotoProperties)
        self.removeDescriptionsButton.clicked.connect(self._removeDescriptionsHandler)
        self.removePropertiesButton.clicked.connect(self._removePropertiesHandler)
        self.generateAlbumButton.clicked.connect(self._generateAlbum)
        self.openAlbumButton.clicked.connect(self._openAlbum)
        self.installTemplateButton.clicked.connect(self._installTemplate)
        self.cancelButton.clicked.connect(self._cancelBackgroundTasks)
        self._photosListFilter.delKeyPressed.connect(self._removePhotosHandler)
        self._photosListFilter.escKeyPressed.connect(self.photosList.clearSelection)
        self._descriptionsListFilter.delKeyPressed.connect(self._removeDescriptionsHandler)
        self._descriptionsListFilter.escKeyPressed.connect(self.descriptionsList.clearSelection)
        self._propertiesListFilter.delKeyPressed.connect(self._removePropertiesHandler)
        self._propertiesListFilter.escKeyPressed.connect(self.propertiesList.clearSelection)
        
        # To make the first item of a QComboBox unselectable:
        #model = combobox.model()
        #firstIndex = model.index(0, combobox.modelColumn(), combobox.rootModelIndex())
        #firstItem = model.itemFromIndex(firstIndex)
        #firstItem.setSelectable(False)

        # To make the background color of QComboBox items to match normal buttons:
        #p = combobox.palette()
        #p.setColor(QtGui.QPalette.Base, p.color(QtGui.QPalette.Button))
        #p.setBrush(QtGui.QPalette.Base, p.brush(QtGui.QPalette.Button))
        #combobox.setPalette(p)

        # To force a QGroupBox's title to the top left, add something like this to the QBroupBox's 
        # stylesheet: QGroupBox::title {subcontrol-position: top left;}

        #self.photosList.currentItemChanged.connect(lambda a,b : print("currentItemChanged"))
        #self.photosList.currentRowChanged.connect(self._b)
        #self.photosList.currentTextChanged.connect(self._c)
        #self.photosList.itemActivated.connect(self._d)
        #self.photosList.itemChanged.connect(self._e)
        #self.photosList.itemClicked.connect(self._f)
        #self.photosList.itemDoubleClicked.connect(self._g)
        #self.photosList.itemEntered.connect(self._h)
        #self.photosList.itemPressed.connect(self._i)
        #self.photosList.itemSelectionChanged.connect(lambda : print("itemSelectionChanged"))


    def closeEvent(self, event):
        """Main window close event handler.  Shutdown the thread pool and save the run-time 
        configuration."""
        self._threads.shutdown()
        self._config.dimensions = (self.size().width(), self.size().height())
        self._config.uiData = self._saveUIData()
        self._config.save()
        event.accept()


    def _saveUIData(self):
        """Retrieve UI data fields that are likely to remain the same between albums."""
        # TODO: generateAlbum should use this code
        data = {}
        # I deliberately don't save title, description or photos because they're likely to change 
        # between albums.  These fields are much more likely to stay the same.
        data["photoResolution"] = tuple(int (s) for s in self.photoSizeButton.currentText().split("x"))
        data["footer"] = self.footerText.toPlainText()
        data["captionFields"] = [self.descriptionsList.item(i).text() for i in range(0, self.descriptionsList.count())]
        data["propertyFields"] = [self.propertiesList.item(i).text() for i in range(0, self.propertiesList.count())]
        return data


    def _restoreUIData(self, uiData):
        """Restore UI data fields that are likely to remain the same between albums."""
        # TODO: use this code when loading albums
        if "photoResolution" in uiData:
            resolution = "x".join(map(str, uiData["photoResolution"]))
            for i in range(0, self.photoSizeButton.count()):
                if resolution == self.photoSizeButton.itemText(i):
                    self.photoSizeButton.setCurrentIndex(i)
                    break
        if "footer" in uiData:
            self.footerText.setPlainText(uiData["footer"])
        if "captionFields" in uiData:
            for prop in uiData["captionFields"]:
                self.descriptionsList.addItem(prop)
        if "propertyFields" in uiData:
            for prop in uiData["propertyFields"]:
                self.propertiesList.addItem(prop)


    def _addPhotosHandler(self, index):
        """Event handler for the addPhotos button"""
        sender = self.sender()
        if self._addPhotosFiles is sender:
            # Browse for photos
            filenames = QtGui.QFileDialog.getOpenFileNames(self, "Select photos", 
                                                       self._config.photoDir, 
                                                       "Images (*.jpg *.jpeg *.png *.tif *.tiff)")
            self._addPhotoFiles(filenames)
            if 0 < len(filenames):
                self._config.photoDir = os.path.dirname(filenames[len(filenames)-1])
        elif self._addPhotosGthumb3 is sender:
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
            print("ERROR: unknown item selected in 'Add Photos' control")


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


    def _showProperties(self):
        """Displays a photo's properties."""
        self.photoProperties.clear()
        # When the user deselects everything, currentRow and currentItem remain the last selected 
        # item.  But selectedItems() is empty.
        if 0 != len(self.photosList.selectedItems()):
            photo = self.photosList.currentItem()
            lineBreak = ""
            for obj in [photo.descriptions, photo.properties]:
                for prop in sorted(obj.keys()):
                    self.photoProperties.insertHtml("%s<strong>%s</strong>: %s" % (lineBreak, prop, obj[prop]))
                    if "" == lineBreak:
                        lineBreak = "<br>"


    def _showPhoto(self, photo):
        """Displays a photo using the system's image viewer."""
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(photo.getPath()))


    def _showError(self, err):
        """Show an error message."""
        QtGui.QMessageBox.question(self, PROGRAM_NAME, err, QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)


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

        # Rebuild the list
        self._addPropertyButtonMenu.clear()
        showAll = self.showAllPropertiesFlag.isChecked()
        for prop in sorted(properties.keys()):
            if showAll or count == properties[prop]:
                self._addPropertyButtonMenu.addAction(prop, self._addPropertyHandler)


    def _updatePhotoDescriptions(self):
        # Figure out what caption fields we have.
        descriptions = {}
        count = self.photosList.count()
        for i in range(count):
            photo = self.photosList.item(i)
            for prop in photo.descriptions.keys():
                if prop in descriptions:
                    descriptions[prop] += 1
                else:
                    descriptions[prop] = 1

        # Rebuild the list
        self._addCaptionButtonMenu.clear()
        showAll = self.showAllDescriptionsFlag.isChecked()
        for prop in sorted(descriptions.keys()):
            if showAll or count == descriptions[prop]:
                self._addCaptionButtonMenu.addAction(prop, self._addCaptionHandler)


    def _addCaptionHandler(self):
        self.descriptionsList.addItem(self.sender().text())


    def _removeDescriptionsHandler(self):
        """Event handler for the removeDescriptions button"""
        for item in self.descriptionsList.selectedItems():
            # removeItemWidget() doesn't seem to work
            self.descriptionsList.takeItem(self.descriptionsList.indexFromItem(item).row())


    def _addPropertyHandler(self):
        self.propertiesList.addItem(self.sender().text())


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
        album["description"] = self.descriptionText.toPlainText()
        album["photoResolution"] = tuple(int(s) for s in self.photoSizeButton.currentText().split("x"))
        album["captionFields"] = [self.descriptionsList.item(i).text() for i in range(0, self.descriptionsList.count())]
        album["propertyFields"] = [self.propertiesList.item(i).text() for i in range(0, self.propertiesList.count())]
        album["photos"] = [self.photosList.item(i).getAlbumJSON() for i in range(0, self.photosList.count())]
        #print(json.dumps(album, indent=2, sort_keys=True))

        # TODO: instead of prompting for a directory, then looking for "album.json" in it, prompt 
        # to save a .json file.

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
                # In Python 3.4, I might be able to use functools.partialmethod to create a generic 
                # wrapper that calls self._incProgressSignal.emit() after an arbitrary method call, 
                # rather than needing to write wrappers for every method call.
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

        # Dismiss the cancellation UI
        self._backgroundCompleteSignal.emit()

        # Close the directory
        os.close(dirFD)


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


    def _installTemplate(self):
        #TODO
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
        if overwritePrompt and QtGui.QMessageBox.Yes == QtGui.QMessageBox.warning(parentWindow, PROGRMA_NAME, overwritePrompt, QtGui.QMessageBox.Yes|QtGui.QMessageBox.No, QtGui.QMessageBox.No):
            return open(fileName, "w", opener=openFunc)
        else:
            raise


def main():
    app = QtGui.QApplication(sys.argv)

    # Check that the Python version is at least 3.3 and that we're on an OS with 
    # /proc/<pid>/fd/<fd>.  Error out if not.
    if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 3):
        QtGui.QMessageBox.critical(None, PROGRAM_NAME, "This program requires Python 3.3 or newer.", QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)
        sys.exit(1)
    try:
        f = open("/proc/%d/fd/0" % (os.getpid()))
        f.close()
    except:
        QtGui.QMessageBox.critical(None, PROGRAM_NAME, "This program currently only runs on Linux.", QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)
        sys.exit(1)

    # Loaded here so that the program will load under Python 2.7 and then error out nicely rather 
    # than crashing with a cryptic stack trace.
    import concurrent.futures
    global concurrent

    with Config() as config:
        wnd = PhotoAlbumUI(config)
        wnd.show()
        sys.exit(app.exec_())

if __name__ == '__main__':
    main()
