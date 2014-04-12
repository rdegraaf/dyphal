#!/usr/bin/python3

"""Server-side data generator for DHTML Photo Album.

AlbumGenerator is a tool to create photo albums using DHTML Photo 
Album.  It can import metadata from a variety of embedded photo tags 
(EXIF, IPTC, etc.) and it understands catalog files created by gThumb 
3.x.  Hopefully the UI is self-explanatory, because there isn't any 
detailed usage documentation at this time.

AlbumGenerator requires Python 3.3 or later, only runs on Linux, and 
requires that the commands 'convert' from the ImageMagick package and 
'exiftool' are available in the current path.
"""
__author__ = "Rennie deGraaf <rennie.degraaf@gmail.com>"
__version__ = "3.0"
__credits__ = ["Rennie deGraaf"]
__date__ = "2014-04-09"

__copyright__ = "Copyright (c) Rennie deGraaf, 2005-2014.  All rights reserved."
__license__ = "GPLv2.0"
__email__ = "rennie.degraaf@gmail.com"

#__all__ = "" # Uncomment to limit the amount of data tha pydoc spews out.


import sys
import os
import os.path
import xml.etree.ElementTree
import concurrent.futures
import threading
import subprocess
import json
import tempfile
import traceback
import functools
import shutil
import urllib.parse

from PyQt4 import QtCore
from PyQt4 import QtGui

from album_generator.ui import *
from album_generator.util import *
from album_generator.photo import *

# These variables may be re-written by the installation script
DATA_PATH = os.path.expanduser("~/.share/AlbumGenerator/")
CONFIG_FILE = os.path.expanduser("~/.config/AlbumGenerator.conf")


class Config(object):
    """Run-time configuration.

    Attributes:
        photoDir (str): The name of the directory from which photos 
                were last imported.
        gthumb3Dir (str): The name of the directory from which a gThumb 
                3 catalog was last imported.
        outputDir (str): The name of the directory where an album was 
                last created.
        photoQuality (int): The quality percentage for resized photos.
        maxWorkers (int): The maximum number of background threads to 
                use.
        dimensions ((int, int)): The current window dimensions.
        uiData (dict): Contents of certain UI fields that were saved 
                from the last session.
        tempDir (tempfile.TemporaryDirectory): A secure temporary 
                directory to hold links to photos and generated files.
        _file (file): A handle to the configuration file.
    """

    PROGRAM_NAME = "Album Generator"
    FILE_FORMAT_VERSION = 1
    THUMB_WIDTH = 160
    THUMB_HEIGHT = 120
    THUMB_QUALITY = 50
    BG_TIMEOUT = 5
    TEMPLATE_FILE_NAMES = ["album.css", "album.js", "back.png", "common.css", "debug.css", 
                           "help.png", "ie8compat.js", "index.html", "lib.js", "next.png", 
                           "photo.css", "placeholder.png", "prev.png"]

    DEFAULT_PHOTO_DIR = os.path.expanduser("~")
    DEFAULT_GTHUMB3_DIR = os.path.expanduser("~/.local/share/gthumb/catalogs")
    DEFAULT_GTHUMB2_DIR = os.path.expanduser("~/.gnome2/gthumb/collections")
    DEFAULT_OUTPUT_DIR = os.path.expanduser("~")
    DEFAULT_PHOTO_QUALITY = 75
    DEFAULT_THREADS = 8

    METADATA_DIR = "metadata"
    PHOTO_DIR = "photos"
    THUMBNAIL_DIR = "thumbnails"

    def __init__(self):
        """Set up run-time configuration.  Load the configuration file 
        and set up shared resources.  Populate any run-time properties 
        not found in the file with sane defaults."""
        # Load the configuration file.  Keep the handle so that we can save to the same file.
        self._file = None
        data = {}
        try:
            ensure_directory(os.path.dirname(CONFIG_FILE))
            # Python's 'r+' mode doesn't create files if they don't already exist.
            self._file = open(CONFIG_FILE, "r+", 
                              opener=lambda path, flags : os.open(path, flags|os.O_CREAT, 0o666))
            data = json.load(self._file)
        except (FileNotFoundError, ValueError):
            # open() can fail with FileNotFoundError if a directory in the path doesn't exist.
            # json.load() can fail with ValueError if the file is empty or otherwise invalid.
            pass
        except Exception:
            # We'll just ignore any other failures and continue without a configuration file.
            (exc_type, exc_value, exc_traceback) = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)

        # Used during operation and stored in the configuration file
        self.photoDir = data["photoDir"] if "photoDir" in data else self.DEFAULT_PHOTO_DIR
        self.gthumb3Dir = data["gthumb3Dir"] if "gthumb3Dir" in data else self.DEFAULT_GTHUMB3_DIR
        #self.gthumb2Dir = data["gthumb2Dir"] if "gthumb2Dir" in data else self.DEFAULT_GTHUMB2_DIR
        self.outputDir = data["outputDir"] if "outputDir" in data else self.DEFAULT_OUTPUT_DIR
        self.photoQuality = self.DEFAULT_PHOTO_QUALITY
        if "photoQuality" in data and 0 < data["photoQuality"] and 100 >= data["photoQuality"]:
            self.photoQuality = data["photoQuality"]

        # Used only at startup and stored in the configuration file
        self.maxWorkers = self.DEFAULT_THREADS
        if "threads" in data and 0 < data["threads"] and 50 >= data["threads"]:
            self.maxWorkers = data["threads"]
        self.dimensions = data["dimensions"] if "dimensions" in data else None
        self.uiData = data["uiData"] if "uiData" in data else None

        # Not stored in the configuration file
        self.tempDir = tempfile.TemporaryDirectory()

    def save(self):
        """Save the current state to the configuration file."""
        # If we couldn't open or create the config file, don't bother saving.
        if None is not self._file:
            data = {}
            data["photoDir"] = self.photoDir
            data["gthumb3Dir"] = self.gthumb3Dir
            data["outputDir"] = self.outputDir
            data["photoQuality"] = self.photoQuality
            data["threads"] = self.maxWorkers
            data["dimensions"] = self.dimensions
            data["uiData"] = self.uiData

            self._file.seek(0)
            self._file.truncate(0)
            json.dump(data, self._file)
            self._file.flush()

    def close(self):
        """Close the configuration file and tear down shared resources."""
        self.tempDir.cleanup()
        self.tempDir = None
        self._file.close()
        self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()


class ListKeyFilter(QtCore.QObject):
    """QT filter to handle certain keypress events."""

    delKeyPressed = QtCore.pyqtSignal() # 'del' key pressed.
    escKeyPressed = QtCore.pyqtSignal() # 'esc' key pressed.
    
    def eventFilter(self, obj, event):
        """Handle 'del' and 'esc' keypress events."""
        if QtCore.QEvent.KeyPress == event.type():
            if QtCore.Qt.Key_Delete == event.key():
                self.delKeyPressed.emit()
                return True
            elif QtCore.Qt.Key_Escape == event.key():
                self.escKeyPressed.emit()
                return True
        return False


class PhotoAlbumUI(QtGui.QMainWindow, Ui_MainWindow):
    """The Photo album generator UI.

    Attributes (not including UI objects):
        _config (Config): The run-time configuration object.
        _threads (concurrent.futures.Executor): The thread pool for 
                background tasks.
        _backgroundTasks (list of concurrent.futures.Future): Pending 
                background tasks.
        _directories (list of (int, str)): Directory file descriptors 
                and link names in use by current background tasks.
        _directoriesLock (threading.Lock): Lock to control access to 
                _directories.
    """

    FILTER_IMAGES = "Images (*.jpeg *.jpg *.png *.tiff *.tif)"
    FILTER_GTHUMB3_CATALOGS = "gThumb catalogs (*.catalog)"
    FILTER_ALBUMS = "Albums (*.json)"

    _addPhotoSignal = QtCore.pyqtSignal(PhotoFile)  # Photo is ready to be added to the UI.
    _showErrorSignal = QtCore.pyqtSignal(str)  # An error message needs to be displayed.
    _incProgressSignal = QtCore.pyqtSignal()  # A background processing step has completed.
    _backgroundCompleteSignal = QtCore.pyqtSignal()  # Background processing has completed.
    _renamePhotosSignal = QtCore.pyqtSignal(list)  # Photos need to be renamed due to collisions.

    def __init__(self, config):
        """Initialize a PhotoAlbumUI.  Hooks up event handlers and 
        performs other UI initialization that the generated code from 
        Designer can't do."""
        super().__init__()
        self._config = config
        self._threads = concurrent.futures.ThreadPoolExecutor(self._config.maxWorkers)
        self._backgroundTasks = None
        self._directories = []
        self._directoriesLock = threading.Lock()

        self.setupUi(self)
        if None is not self._config.dimensions:
            self.resize(*self._config.dimensions)
        if None is not self._config.uiData:
            self._restoreUIData(self._config.uiData)
        self.progressBar.setVisible(False)
        self.cancelButton.setVisible(False)

        # Set the sizes of the photo list and properties within the splitter.
        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)

        # Set up the menu for the "Add Photos" button
        self._addPhotosButtonMenu = QtGui.QMenu(self.addPhotosButton)
        self._addPhotosFiles = QtGui.QAction("Add Files...", self._addPhotosButtonMenu)
        self._addPhotosGthumb3 = QtGui.QAction("Add a gThumb 3 Catalog...", 
                                               self._addPhotosButtonMenu)
        self._addPhotosButtonMenu.addAction(self._addPhotosFiles)
        self._addPhotosButtonMenu.addAction(self._addPhotosGthumb3)
        self.addPhotosButton.setMenu(self._addPhotosButtonMenu)

        # Set up the menu for the "Add Caption" button
        self._addCaptionButtonMenu = QtGui.QMenu(self.addCaptionButton)
        self.addCaptionButton.setMenu(self._addCaptionButtonMenu)

        # Set up the menu for the "Add Property" button
        self._addPropertyButtonMenu = QtGui.QMenu(self.addPropertyButton)
        self.addPropertyButton.setMenu(self._addPropertyButtonMenu)

        # Listen for keyboard events in photosList, captionsList, and propertiesList
        self._photosListFilter = ListKeyFilter()
        self.photosList.installEventFilter(self._photosListFilter)
        self._captionsListFilter = ListKeyFilter()
        self.captionsList.installEventFilter(self._captionsListFilter)
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
        self.showAllCaptionsFlag.stateChanged.connect(self._updatePhotoCaptions)
        self.showAllPropertiesFlag.stateChanged.connect(self._updatePhotoProperties)
        self.removeCaptionsButton.clicked.connect(self._removeCaptionsHandler)
        self.removePropertiesButton.clicked.connect(self._removePropertiesHandler)
        self.generateAlbumButton.clicked.connect(self._generateAlbum)
        self.openAlbumButton.clicked.connect(self._openAlbum)
        self.installTemplateButton.clicked.connect(self._installTemplate)
        self.cancelButton.clicked.connect(self._cancelBackgroundTasks)
        self._photosListFilter.delKeyPressed.connect(self._removePhotosHandler)
        self._photosListFilter.escKeyPressed.connect(self.photosList.clearSelection)
        self._captionsListFilter.delKeyPressed.connect(self._removeCaptionsHandler)
        self._captionsListFilter.escKeyPressed.connect(self.captionsList.clearSelection)
        self._propertiesListFilter.delKeyPressed.connect(self._removePropertiesHandler)
        self._propertiesListFilter.escKeyPressed.connect(self.propertiesList.clearSelection)
        self._renamePhotosSignal.connect(self._renamePhotos)

    def closeEvent(self, event):
        """Main window close event handler.  Shutdown the thread pool 
        and save the run-time configuration."""
        self._threads.shutdown()
        self._config.dimensions = (self.size().width(), self.size().height())
        self._config.uiData = self._saveUIData()
        self._config.save()
        event.accept()

    def _saveUIData(self):
        """Retrieve UI data fields that are likely to remain the same 
        between albums."""
        data = {}
        # I deliberately don't save title, caption or photos because they're likely to change 
        # between albums.  These fields are much more likely to stay the same.
        data["photoResolution"] = \
            tuple(int(s) for s in self.photoSizeButton.currentText().split("x"))
        data["footer"] = self.footerText.toPlainText()
        data["captionFields"] = \
            [self.captionsList.item(i).text() for i in range(0, self.captionsList.count())]
        data["propertyFields"] = \
            [self.propertiesList.item(i).text() for i in range(0, self.propertiesList.count())]
        return data

    def _restoreUIData(self, ui_data, require_fields=False):
        """Restore UI data fields that are likely to remain the same 
        between albums."""
        if require_fields or "photoResolution" in ui_data:
            resolution = "x".join([str(s) for s in ui_data["photoResolution"]])
            for i in range(0, self.photoSizeButton.count()):
                if resolution == self.photoSizeButton.itemText(i):
                    self.photoSizeButton.setCurrentIndex(i)
                    break
        if require_fields or "footer" in ui_data:
            self.footerText.setPlainText(ui_data["footer"])
        if require_fields or "captionFields" in ui_data:
            self.captionsList.clear()
            for prop in ui_data["captionFields"]:
                self.captionsList.addItem(prop)
        if require_fields or "propertyFields" in ui_data:
            self.propertiesList.clear()
            for prop in ui_data["propertyFields"]:
                self.propertiesList.addItem(prop)

    def _addPhotosHandler(self, index):
        """Prompt the user for photos to add to the album, then load 
        them."""
        sender = self.sender()
        if self._addPhotosFiles is sender:
            # Browse for photos
            file_names = QtGui.QFileDialog.getOpenFileNames(self, "Select photos", 
                                                            self._config.photoDir, 
                                                            self.FILTER_IMAGES)
            self._addPhotoFiles([(name, os.path.basename(name)) for name in file_names])
            if 0 < len(file_names):
                self._config.photoDir = os.path.dirname(file_names[len(file_names)-1])
        elif self._addPhotosGthumb3 is sender:
            # Add a gThumb 3 catalog
            catalog_file_name = QtGui.QFileDialog.getOpenFileName(self, "Select catalog", 
                                                               self._config.gthumb3Dir, 
                                                               self.FILTER_GTHUMB3_CATALOGS)
            # The QT documentation says that getOpenFileName returns a null string on cancel.  But 
            # it returns an empty string here.  Maybe that's a PyQt bug?
            if "" != catalog_file_name:
                tree = xml.etree.ElementTree.parse(catalog_file_name)
                # Files appear in arbitrary order in a gThumb 3 catalog file.  
                # I assume that the display order is the names sorted alphabetically.
                filenames = sorted([QtCore.QUrl(elmt.attrib["uri"]).toLocalFile() 
                                    for elmt in tree.getroot().iter("file")])
                self._addPhotoFiles([(name, os.path.basename(name)) for name in filenames])
                self._config.gthumb3Dir = os.path.dirname(catalog_file_name)
        else:
            print("ERROR: unknown item selected in 'Add Photos' control")

    def _addPhotoFiles(self, filenames):
        """Start background tasks to load a list of photos."""
        if 0 < len(filenames):
            self._backgroundInit(len(filenames))
            tasks = []
            task = None
            for (path, name) in filenames:
                task = self._threads.submit(self._bgAddPhoto, path, name, task)
                task.photoName = path
                tasks.append(task)
            self._threads.submit(functools.partial(handle_exceptions, self._bgAddPhotoComplete), 
                                 tasks)
            self._backgroundStart(tasks)

    def _removePhotosHandler(self):
        """Remove the currently selected photos from the album."""
        for item in self.photosList.selectedItems():
            # removeItemWidget() doesn't seem to work
            photo = self.photosList.takeItem(self.photosList.indexFromItem(item).row())
            photo.release()

        # Update the available properties list
        self.showAllPropertiesFlag.stateChanged.emit(0)
        self.showAllCaptionsFlag.stateChanged.emit(0)

    def _addPhoto(self, photo):
        """Add a photo that has been loaded to the album."""
        self.photosList.addItem(photo)

    def _showProperties(self):
        """Display the properties of the most recently selected photo."""
        self.photoProperties.clear()
        # When the user deselects everything, currentRow and currentItem remain the last selected 
        # item.  But selectedItems() is empty.
        if 0 != len(self.photosList.selectedItems()) and None is not self.photosList.currentItem():
            photo = self.photosList.currentItem()
            line_break = ""
            for obj in [photo.captions, photo.properties]:
                for prop in sorted(obj.keys()):
                    self.photoProperties.insertHtml("%s<strong>%s</strong>: %s" % 
                                                    (line_break, prop, obj[prop]))
                    if "" == line_break:
                        line_break = "<br>"

    def _showPhoto(self, photo):
        """Display a photo using the system's image viewer."""
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(photo.getPath()))

    def _showError(self, err):
        """Show an error message."""
        QtGui.QMessageBox.question(self, Config.PROGRAM_NAME, err, QtGui.QMessageBox.Ok, 
                                   QtGui.QMessageBox.Ok)

    def _incProgress(self):
        """Increment the progress bar counter."""
        self.progressBar.setValue(self.progressBar.value() + 1)

    def _backgroundInit(self, steps):
        """Initialize the progress bar for a background action.  This 
        must occur before any background tasks can run."""
        # Make sure that we're not already running a background task. 
        assert(None is self._backgroundTasks)
        self.generateAlbumButton.setVisible(False)
        self.progressBar.setMaximum(steps)

    def _backgroundStart(self, tasks):
        """Show the cancellation UI.  Don't do this until after the 
        background tasks are registered so that there's something to 
        cancel."""
        self._backgroundTasks = tasks
        self.progressBar.setValue(0)
        self.progressBar.setVisible(True)
        self.cancelButton.setVisible(True)

    def _backgroundComplete(self):
        """Dismiss the cancellation UI."""
        self.cancelButton.setVisible(False)
        self.progressBar.setVisible(False)
        self.generateAlbumButton.setVisible(True)
        self._backgroundTasks = None

    def _bgAddPhoto(self, path, name, prev_task):
        """Background task to load a photo and signal the UI to add it 
        to the album when done."""
        photo = PhotoFile(path, name, self._config)
        photo.addRef()
        # Wait for the previous photo to be loaded so that photos are added to the list in the 
        # correct order.
        if None is not prev_task:
            concurrent.futures.wait([prev_task])
        self._addPhotoSignal.emit(photo)
        self._incProgressSignal.emit()

    def _bgAddPhotoComplete(self, tasks):
        """Background task to display any errors encountered while 
        loading photos, prompt the user to rename any photos with non-
        unique names, and update the lists of available properties and 
        captions."""
        # Wait for the addPhoto tasks to complete.
        (done, not_done) = concurrent.futures.wait(tasks)
        assert(0 == len(not_done))

        # Display any error messages and find any files that need to be renamed
        errors = []
        rename_photos = []
        for task in done:
            try:
                task.result()
            except FileNotFoundError as e:
                # Either exiftool or the photo was missing.
                if "exiftool" == e.filename:
                    errors.append("Error executing 'exiftool'.  Is it installed?")
                else:
                    errors.append("Error opening photo " + e.filename)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # Exiftool failed or timed out.
                errors.append("Error reading metadata from photo " + task.photoName)
            except FileExistsError:
                # The symlink target already exists, implying a duplicate file name.
                rename_photos.append(task.photoName)
            except concurrent.futures.CancelledError:
                # The task was cancelled.
                pass
            except:
                (exc_type, exc_value, exc_traceback) = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                errors.append(str(exc_type) + ": " + str(exc_value))
        if 0 != len(errors):
            self._showErrorSignal.emit(str(len(errors)) +
                                       " errors were encountered loading files:\n" +
                                       "\n".join(errors))

        # Update the available properties list
        self.showAllPropertiesFlag.stateChanged.emit(0)
        self.showAllCaptionsFlag.stateChanged.emit(0)

        # Get the user to handle any photos that need renaming
        if 0 != len(rename_photos):
            self._renamePhotosSignal.emit(rename_photos)

        # re-enable any disabled buttons
        self._backgroundCompleteSignal.emit()

    def _updatePhotoProperties(self):
        """Rebuild the list of properties available in the currently 
        loaded photos."""
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
        show_all = self.showAllPropertiesFlag.isChecked()
        for prop in sorted(properties.keys()):
            if show_all or count == properties[prop]:
                self._addPropertyButtonMenu.addAction(prop, self._addPropertyHandler)

    def _updatePhotoCaptions(self):
        """Rebuild the list of captions available in the currently 
        loaded photos."""
        # Figure out what caption fields we have.
        captions = {}
        count = self.photosList.count()
        for i in range(count):
            photo = self.photosList.item(i)
            for prop in photo.captions.keys():
                if prop in captions:
                    captions[prop] += 1
                else:
                    captions[prop] = 1

        # Rebuild the list
        self._addCaptionButtonMenu.clear()
        show_all = self.showAllCaptionsFlag.isChecked()
        for prop in sorted(captions.keys()):
            if show_all or count == captions[prop]:
                self._addCaptionButtonMenu.addAction(prop, self._addCaptionHandler)

    def _addCaptionHandler(self):
        """Add the selected caption field to the album captions."""
        if 0 == len(self.captionsList.findItems(self.sender().text(), 
                                                QtCore.Qt.MatchFixedString)):
            self.captionsList.addItem(self.sender().text())

    def _removeCaptionsHandler(self):
        """Remove the selected caption fields from the album captions."""
        for item in self.captionsList.selectedItems():
            # removeItemWidget() doesn't seem to work
            self.captionsList.takeItem(self.captionsList.indexFromItem(item).row())

    def _addPropertyHandler(self):
        """Add the selected property field to the album properties."""
        if 0 == len(self.propertiesList.findItems(self.sender().text(), 
                                                  QtCore.Qt.MatchFixedString)):
            self.propertiesList.addItem(self.sender().text())

    def _removePropertiesHandler(self):
        """Remove the selected properties fields from the album 
        properties."""
        for item in self.propertiesList.selectedItems():
            # removeItemWidget() doesn't seem to work
            self.propertiesList.takeItem(self.propertiesList.indexFromItem(item).row())

    def _generateAlbum(self):
        """Save an album.  Prompt the user for a file name, then spawn 
        background tasks to generate album and photo JSON, thumbnails, 
        and down-scaled photos.  """
        album = self._saveUIData()
        album["albumVersion"] = Config.FILE_FORMAT_VERSION
        album["metadataDir"] = urllib.parse.quote(Config.METADATA_DIR + "/")
        album["title"] = self.titleText.toPlainText()
        album["description"] = self.descriptionText.toPlainText()
        album["photos"] = \
            [self.photosList.item(i).getAlbumJSON() for i in range(0, self.photosList.count())]

        # Get the output file name
        album_file_name = QtGui.QFileDialog.getSaveFileName(self, "Album File", 
                                                            self._config.outputDir, 
                                                            self.FILTER_ALBUMS)
        album_dir_name = os.path.dirname(album_file_name)

        # To prevent the output directory from being changed while generating files, we do the 
        # following:
        #  1. Create a secure temporary directory.
        #  2. Open the output directory.  Get its file descriptor.
        #  3. Construct the /proc/<pid>/fd/<fd> path to the directory using the file descriptor.
        #  4. Create a symlink from the temporary directory to the /proc path.  The link's name is 
        #     unique but predictable; that's ok because the directory is secure.
        #  5. Use the symlink as the path when creating files.

        self._backgroundInit(3 * self.photosList.count() + 5)
        tasks = []

        # Create the output directories.
        # We read and write self._directories from different threads, but there's no race because 
        # the read task is blocked until after the write tasks complete.
        assert(0 == len(self._directories))
        album_dir_path = os.path.join(self._config.tempDir.name, "album")
        album_dir_task = self._threads.submit(self._bgCreateOutputDirectory, album_dir_name, 
                                              album_dir_path)
        tasks.append(album_dir_task)
        metadata_dir_path = os.path.join(self._config.tempDir.name, Config.METADATA_DIR)
        metadata_dir_task = None
        if 0 != len(Config.METADATA_DIR):
            metadata_dir_task = self._threads.submit(self._bgCreateOutputDirectory, 
                                                     os.path.join(album_dir_name, 
                                                                  Config.METADATA_DIR), 
                                                     metadata_dir_path)
            tasks.append(metadata_dir_task)
        photo_dir_path = os.path.join(self._config.tempDir.name, Config.PHOTO_DIR)
        photo_dir_task = None
        if 0 != len(Config.PHOTO_DIR):
            photo_dir_task = self._threads.submit(self._bgCreateOutputDirectory, 
                                                  os.path.join(album_dir_name, 
                                                               Config.PHOTO_DIR), 
                                                  photo_dir_path)
            tasks.append(photo_dir_task)
        thumbnail_dir_path = os.path.join(self._config.tempDir.name, Config.THUMBNAIL_DIR)
        thumbnail_dir_task = None
        if 0 != len(Config.THUMBNAIL_DIR):
            thumbnail_dir_task = self._threads.submit(self._bgCreateOutputDirectory, 
                                                      os.path.join(album_dir_name, 
                                                                   Config.THUMBNAIL_DIR),
                                                      thumbnail_dir_path)
            tasks.append(thumbnail_dir_task)

        # Create the album JSON file
        tasks.append(self._threads.submit(self._bgGenerateAlbum, album, os.path.join(
                                album_dir_path, os.path.basename(album_file_name)), album_dir_task))

        # Create the metadata, thumbnail, and image for each photo.
        count = self.photosList.count()
        if 0 < count:
            captions = album["captionFields"]
            properties = album["propertyFields"]
            for i in range(0, count):
                photo = self.photosList.item(i)
                # In Python 3.4, I might be able to use functools.partialmethod to create a generic 
                # wrapper that calls self._incProgressSignal.emit() after an arbitrary method call, 
                # rather than needing to write wrappers for every method call.
                task = self._threads.submit(self._bgGeneratePhotoJSON, photo, metadata_dir_path, 
                                            album["photoResolution"][0], 
                                            album["photoResolution"][1], captions, properties, 
                                            metadata_dir_task)
                photo.addRef()
                task.photoName = photo.getPath()
                tasks.append(task)
                task = self._threads.submit(self._bgGeneratePhoto, photo, photo_dir_path, 
                                            album["photoResolution"][0], 
                                            album["photoResolution"][1], self._config.photoQuality, 
                                            photo_dir_task)
                photo.addRef()
                task.photoName = photo.getPath()
                tasks.append(task)
                task = self._threads.submit(self._bgGenerateThumbnail, photo, thumbnail_dir_path, 
                                            Config.THUMB_WIDTH, Config.THUMB_HEIGHT, 
                                            Config.THUMB_QUALITY, thumbnail_dir_task)
                photo.addRef()
                task.photoName = photo.getPath()
                tasks.append(task)

        self._threads.submit(functools.partial(handle_exceptions, self._bgTasksComplete), tasks, 
                             "generating the album")
        self._backgroundStart(tasks)

        self._config.outputDir = album_dir_name

    def _bgCreateOutputDirectory(self, dir_path, link_path):
        """Background task to create a directory and link to it from 
        the temporary directory."""
        ensure_directory(dir_path)
        dir_fd = os.open(dir_path, os.O_RDONLY)
        with self._directoriesLock:
            self._directories.append((dir_fd, link_path))
        os.symlink("/proc/%d/fd/%d" % (os.getpid(), dir_fd), link_path)
        self._incProgressSignal.emit()

    def _bgGenerateAlbum(self, album, album_file_name, dir_creation_task):
        """Background task to generate an album JSON file."""
        if None is not dir_creation_task:
            concurrent.futures.wait([dir_creation_task])
        with open(album_file_name, "w") as album_file:
            json.dump(album, album_file)
        self._incProgressSignal.emit()

    def _bgTasksComplete(self, tasks, message):
        """Background task to display any errors encountered while 
        executing background tasks and clean up any file descriptors 
        and links that were needed by the background tasks."""
        # Wait for the tasks to complete.
        (done, not_done) = concurrent.futures.wait(tasks)
        assert(0 == len(not_done))

        # Close any file descriptors and remove any symlinks.  Ignore errors.
        with self._directoriesLock:
            for (fd, link) in self._directories:
                try:
                    os.unlink(link)
                except OSError:
                    pass
                try:
                    os.close(fd)
                except OSError:
                    pass
            self._directories = []

        # Display any error messages
        errors = []
        for task in done:
            try:
                task.result()
            except concurrent.futures.CancelledError:
                pass
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # convert failed or timed out.
                errors.append("Error resizing " + task.photoName)
            except:
                (exc_type, exc_value, exc_traceback) = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                errors.append(str(exc_type) + ": " + str(exc_value))
        if 0 != len(errors):
            self._showErrorSignal.emit("%d errors were encountered while %s:\n" % 
                                       (len(errors), message) + "\n".join(errors))

        # Dismiss the cancellation UI
        self._backgroundCompleteSignal.emit()

    def _bgGeneratePhotoJSON(self, photo, out_dir_name, width, height, captions, properties, 
                             dir_creation_task):
        """Background task to generate a photo JSON file."""
        # Wait for the directory to be created, then generate the photo JSON
        if None is not dir_creation_task:
            concurrent.futures.wait([dir_creation_task])
        photo.generateJSON(out_dir_name, width, height, captions, properties)
        photo.release()
        self._incProgressSignal.emit()

    def _bgGeneratePhoto(self, photo, out_dir_name, width, height, quality, dir_creation_task):
        """Background task to generate a down-scaled photo."""
        # Wait for the directory to be created, then generate the photo
        if None is not dir_creation_task:
            concurrent.futures.wait([dir_creation_task])
        photo.generatePhoto(out_dir_name, width, height, quality)
        photo.release()
        self._incProgressSignal.emit()

    def _bgGenerateThumbnail(self, photo, out_dir_name, width, height, quality, dir_creation_task):
        """Background task to generate a photo thumbnail."""
        # Wait for the directory to be created, then generate the thumbnail
        if None is not dir_creation_task:
            concurrent.futures.wait([dir_creation_task])
        photo.generateThumbnail(out_dir_name, width, height, quality)
        photo.release()
        self._incProgressSignal.emit()

    def _openAlbum(self):
        """Load an album JSON file and populate the UI with its 
        contents."""
        album_file_name = QtGui.QFileDialog.getOpenFileName(self, "Select album", 
                                                            self._config.outputDir, 
                                                            self.FILTER_ALBUMS)
        # The QT documentation says that getOpenFileName returns a null string on cancel.  But it
        # returns an empty string here.  Maybe that's a PyQt bug?
        if "" != album_file_name:
            try:
                with open(album_file_name) as album_file:
                    data = json.load(album_file)
                    if "albumVersion" in data and Config.FILE_FORMAT_VERSION == data["albumVersion"]:
                        self._restoreUIData(data, require_fields=True)
                        self.titleText.setPlainText(data["title"])
                        self.descriptionText.setPlainText(data["description"])
                        photos = []
                        for photo in data["photos"]:
                            path = urllib.parse.unquote(photo["path"])
                            photos.append((os.path.expanduser(path), os.path.basename(path)))
                        self._addPhotoFiles(photos)
                        return
                    raise ValueError("Invalid album file")
            except (KeyError, ValueError, OSError):
                QtGui.QMessageBox.warning(None, Config.PROGRAM_NAME, 
                                          "Unable to load an album from '%s'." % 
                                          (os.path.basename(album_file_name)), 
                                          QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)

    def _installTemplate(self):
        """Install the photo album template files.  Prompt the user for 
        a directory, then copy the files over on background threads."""
        # Get the destination directory
        # The KDE directory chooser dialog is all kinds of buggy: it doesn't expand the current 
        # directory on open, and double-clicking on a directory prompts the user to rename it. So 
        # I'm using the QT directory chooser instead.
        out_dir = QtGui.QFileDialog.getExistingDirectory(self, "Album directory", 
                                                         self._config.outputDir, 
                                                         QtGui.QFileDialog.ShowDirsOnly|
                                                         QtGui.QFileDialog.DontUseNativeDialog)

        self._backgroundInit(len(Config.TEMPLATE_FILE_NAMES) + 1)
        tasks = []

        # Open the output directory so that it can't change under us.
        assert(0 == len(self._directories))
        album_dir_path = os.path.join(self._config.tempDir.name, "album")
        album_dir_task = self._threads.submit(self._bgCreateOutputDirectory, out_dir, 
                                              album_dir_path)
        tasks.append(album_dir_task)

        # Spawn background tasks to do the copying.
        for f in Config.TEMPLATE_FILE_NAMES:
            tasks.append(self._threads.submit(self._bgCopyFile, os.path.join(DATA_PATH, f), 
                                              os.path.join(album_dir_path, f), album_dir_task))

        self._threads.submit(functools.partial(handle_exceptions, self._bgTasksComplete, tasks, 
                                               "installing the template"))
        self._backgroundStart(tasks)

    def _bgCopyFile(self, source, destination, dir_creation_task):
        """Background task to copy a file."""
        # Wait for the directory to be created, then copy the file
        if None is not dir_creation_task:
            concurrent.futures.wait([dir_creation_task])
        shutil.copyfile(source, destination)
        self._incProgressSignal.emit()

    def _cancelBackgroundTasks(self):
        """Attempt to cancel any pending background tasks."""
        if None is not self._backgroundTasks:
            for task in self._backgroundTasks:
                task.cancel()
        self._backgroundComplete()

    def _renamePhotos(self, photo_names):
        """Prompt the user to rename photos that share names with other 
        photos that have already been loaded, then attempt to load them 
        again using the new names."""
        prompt_dialog = QtGui.QMessageBox(self)
        prompt_dialog.setIcon(QtGui.QMessageBox.Question)
        rename_button = prompt_dialog.addButton("Rename...", QtGui.QMessageBox.YesRole)
        remove_button = prompt_dialog.addButton("Remove", QtGui.QMessageBox.NoRole)

        # Get new names for the files
        new_names = []
        for photoName in photo_names:
            prompt_dialog.setText("There is already a photo with the name %s in the album.  " \
                                 "Would you like to rename or remove the new one?" % (photoName))
            prompt_dialog.exec_()
            if rename_button is prompt_dialog.clickedButton():
                # It seems that if I try to re-use the QFileDialog, changing the selected file has 
                # no effect.
                file_dialog = QtGui.QFileDialog(self, "New photo name", self._config.tempDir.name, 
                                                self.FILTER_IMAGES)
                file_dialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)
                file_dialog.setFileMode(QtGui.QFileDialog.AnyFile)
                # The PhotoFile class won't let the user overwrite anything, but with overwrite 
                # confirmations on, QFileDialog prompts to overwrite the directory if a user hits 
                # "Save" with nothing selected.  Disabling confirmation avoids this.
                file_dialog.setOption(QtGui.QFileDialog.DontConfirmOverwrite)
                file_dialog.selectFile(os.path.basename(photoName))
                file_dialog.exec_()
                if 0 < len(file_dialog.selectedFiles()):
                    assert(1 == len(file_dialog.selectedFiles()))
                    new_file_name = file_dialog.selectedFiles()[0]
                    new_names.append((photoName, os.path.basename(new_file_name)))

        # Spawn background tasks to load the files using the new names.
        self._addPhotoFiles(new_names)


def main():
    """Main."""
    app = QtGui.QApplication(sys.argv)

    # Check that the Python version is at least 3.3, that we're on an OS with /proc/<pid>/fd/<fd>, 
    # and that exiftool and convert are available.  Error out if not.
    if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 3):
        QtGui.QMessageBox.critical(None, Config.PROGRAM_NAME, 
                                   "This program requires Python 3.3 or newer.", 
                                   QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)
        sys.exit(1)
    try:
        with open("/proc/%d/fd/0" % (os.getpid())) as f:
            pass
    except IOError:
        QtGui.QMessageBox.critical(None, Config.PROGRAM_NAME, 
                                   "This program currently only runs on Linux.", 
                                   QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)
        sys.exit(1)
    try:
        subprocess.check_call(["exiftool", "-ver"], stdout=subprocess.DEVNULL, timeout=1)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        QtGui.QMessageBox.critical(None, Config.PROGRAM_NAME, 
                                   "This program requires that 'exiftool' be available in your " \
                                   "PATH.", QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)
        sys.exit(1)
    try:
        subprocess.check_call(["convert", "--version"], stdout=subprocess.DEVNULL, timeout=1)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        QtGui.QMessageBox.critical(None, Config.PROGRAM_NAME, "This program requires that 'convert' " \
                                   "from the 'ImageMagick' package be available in your PATH.", 
                                   QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)
        sys.exit(1)

    with Config() as config:
        wnd = PhotoAlbumUI(config)
        wnd.show()
        sys.exit(app.exec_())


if __name__ == '__main__':
    main()
