#!/usr/bin/python3

"""Server-side data generator for Dyphal, the Dynamic Photo Album.
Copyright (c) Rennie deGraaf, 2005-2021.

DyphalGenerator is a tool to create photo albums to display using 
Dyphal.  It can import metadata from a variety of embedded photo tags 
(EXIF, IPTC, etc.) and it understands catalog files created by gThumb 
3.x.  Hopefully the UI is self-explanatory, because there isn't any 
detailed usage documentation at this time.

DyphalGenerator requires Python 3.3 or later, only runs on Linux, and 
requires that the commands 'convert' from the ImageMagick package and 
'exiftool' are available in the current path.

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
__version__ = "VERSION"
__date__ = "DATE"

#__all__ = "" # Uncomment to limit the amount of data that pydoc spews out.


import sys
import os
import os.path
import xml.etree.ElementTree
import concurrent.futures
import subprocess
import json
import tempfile
import traceback
import functools
import shutil
import urllib.parse

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from dyphal.ui import Ui_MainWindow
from dyphal.about import Ui_AboutDialog
from dyphal.util import DirectoryHandleList, handle_exceptions, ensure_directory
from dyphal.photo import PhotoFile
from dyphal.album import Album, ParseError, SaveError

# These variables may be re-written by the installation script
DATA_PATH = os.path.expanduser("~/.share/dyphal/")
CONFIG_PATH = os.path.expanduser("~/.config/")
CONFIG_NAME = "DyphalGenerator.conf"


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
        _umask (int): Saved umask.
    """

    PROGRAM_NAME = "Dyphal Generator"
    THUMB_WIDTH = 160
    THUMB_HEIGHT = 120
    THUMB_QUALITY = 50
    BG_TIMEOUT = 5
    TEMPLATE_FILE_NAMES = ["album.css", "back.png", "common.css", "debug.css", "dyphal.js", 
                           "help.png", "index.html", "javascript.html", "next.png", 
                           "photo.css", "placeholder.png", "prev.png", "README.html"]

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
        self._umask = os.umask(0o22)
        try:
            ensure_directory(CONFIG_PATH)
            # Python's 'r+' mode doesn't create files if they don't already exist.
            self._file = open(os.path.join(CONFIG_PATH, CONFIG_NAME), "r+", 
                              opener=lambda path, flags: os.open(path, flags|os.O_CREAT, 0o666))
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
        ideal_thread_count = QtCore.QThread.idealThreadCount()
        if 0 < ideal_thread_count:
            # Some tasks are I/O-bound and some are CPU-bound, so let's go with
            # twice the number of CPU cores.
            self.maxWorkers = 2 * ideal_thread_count
        else:
            self.maxWorkers = self.DEFAULT_THREADS
        if "threads" in data and 0 < data["threads"] and 50 >= data["threads"]:
            self.maxWorkers = data["threads"]
        self.dimensions = data["dimensions"] if "dimensions" in data else None
        self.uiData = data["uiData"] if "uiData" in data else None

        # Not stored in the configuration file
        self.tempDir = tempfile.TemporaryDirectory()

        # Do we have /prod/pid/fd?
        try:
            with open("/proc/%d/fd/0" % (os.getpid())) as fh:
                self.haveProcPid = True
        except (FileNotFoundException, os.error):
            self.haveProcPid = False

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
            json.dump(data, self._file, sort_keys=True)
            self._file.flush()

    def close(self):
        """Close the configuration file and tear down shared resources."""
        self.tempDir.cleanup()
        self.tempDir = None
        self._file.close()
        self._file = None
        os.umask(self._umask)

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


class DyphalUI(QtWidgets.QMainWindow, Ui_MainWindow):
    """The Dyphal Generator UI.

    Attributes (not including UI objects):
        _config (Config): The run-time configuration object.
        _threads (concurrent.futures.Executor): The thread pool for 
                background tasks.
        _backgroundCount (int): The number of background activities 
                (*not* tasks) that are pending.
        _backgroundTasks (list of concurrent.futures.Future): Pending 
                background tasks.
        _currentAlbumFileName (str): The name of the current album file.
        _dirty (bool): True if the album data has changed since the 
                last save; false otherwise.
    """

    FILTER_IMAGES = "Images (*.jpeg *.jpg *.png *.tiff *.tif)"
    FILTER_GTHUMB3_CATALOGS = "gThumb catalogs (*.catalog)"
    FILTER_ALBUMS = "Albums (*.dyphal);;JSON Albums (*.json);;All (*.*)"

    _addPhotoSignal = QtCore.pyqtSignal(PhotoFile, bool)  # A photo is ready to be added to the UI.
    _showErrorSignal = QtCore.pyqtSignal(str)  # An error message needs to be displayed.
    _incProgressSignal = QtCore.pyqtSignal()  # A background processing step has completed.
    _backgroundCompleteSignal = QtCore.pyqtSignal(bool)  # Background processing has completed.
    _renamePhotosSignal = QtCore.pyqtSignal(list)  # Photos need to be renamed due to collisions.
    _setAlbumDataSignal = QtCore.pyqtSignal(str, dict)  # An album has been loaded.
    _closeSignal = QtCore.pyqtSignal() # Program exit was requested from a background thread.
    _dirtySignal = QtCore.pyqtSignal(bool) # A background thread dirtied or undirtied the album.

    def __init__(self, config):
        """Initialize a DyphalUI.  Hooks up event handlers and 
        performs other UI initialization that the generated code from 
        Designer can't do."""
        super().__init__()
        self._config = config
        self._threads = concurrent.futures.ThreadPoolExecutor(self._config.maxWorkers)
        self._backgroundCount = 0
        self._backgroundTasks = None
        self._currentAlbumFileName = None

        self.setupUi(self)
        if None is not self._config.dimensions:
            self.resize(*self._config.dimensions)
        if None is not self._config.uiData:
            self._restoreUIData(self._config.uiData)
        self.progressBar.setVisible(False)
        self.cancelButton.setVisible(False)
        self.generateAlbumButton.setVisible(False)
        self._dirty = False

        # Set the sizes of the photo list and properties within the splitter.
        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)

        # Set up the menu for the "Add Photos" button
        self._addPhotosButtonMenu = QtWidgets.QMenu(self.addPhotosButton)
        self._addPhotosFiles = QtWidgets.QAction("Add Files...", self._addPhotosButtonMenu)
        self._addPhotosGthumb3 = QtWidgets.QAction("Add a gThumb 3 Catalog...", 
                                                   self._addPhotosButtonMenu)
        self._addPhotosButtonMenu.addAction(self._addPhotosFiles)
        self._addPhotosButtonMenu.addAction(self._addPhotosGthumb3)
        self.addPhotosButton.setMenu(self._addPhotosButtonMenu)

        # Set up the menu for the "Add Caption" button
        self._addCaptionButtonMenu = QtWidgets.QMenu(self.addCaptionButton)
        self.addCaptionButton.setMenu(self._addCaptionButtonMenu)

        # Set up the menu for the "Add Property" button
        self._addPropertyButtonMenu = QtWidgets.QMenu(self.addPropertyButton)
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
        self.newAlbumButton.clicked.connect(self._newAlbum)
        self.openAlbumButton.clicked.connect(self._openAlbum)
        self.installTemplateButton.clicked.connect(self._installTemplate)
        self.cancelButton.clicked.connect(self._cancelBackgroundTasks)
        self.aboutButton.clicked.connect(self._about)
        self._photosListFilter.delKeyPressed.connect(self._removePhotosHandler)
        self._photosListFilter.escKeyPressed.connect(self.photosList.clearSelection)
        self._captionsListFilter.delKeyPressed.connect(self._removeCaptionsHandler)
        self._captionsListFilter.escKeyPressed.connect(self.captionsList.clearSelection)
        self._propertiesListFilter.delKeyPressed.connect(self._removePropertiesHandler)
        self._propertiesListFilter.escKeyPressed.connect(self.propertiesList.clearSelection)
        self._renamePhotosSignal.connect(self._renamePhotos)
        self._setAlbumDataSignal.connect(self._setAlbumData)
        self._closeSignal.connect(self.close)
        self.photoSizeButton.currentIndexChanged.connect(lambda: self._setDirty())
        self.titleText.textChanged.connect(self._setDirty)
        self.footerText.textChanged.connect(self._setDirty)
        self.descriptionText.textChanged.connect(self._setDirty)
        self._dirtySignal.connect(self._setDirty)

    def _setDirty(self, dirty=True):
        """Marks the current album as having changed."""
        self._dirty = dirty

    def _bgExit(self, pending_tasks):
        """Background task to trigger program exit."""
        if None is not pending_tasks:
            concurrent.futures.wait(pending_tasks)
        self._backgroundCompleteSignal.emit(True)
        # self.close() can't be called from a background thread.
        self._closeSignal.emit()

    def closeEvent(self, event):
        """Main window close event handler.  Shutdown the thread pool 
        and save the run-time configuration."""

        # Prompt if the album is dirty.
        if self._dirty and 0 < self.photosList.count() \
           and QtWidgets.QMessageBox.No == QtWidgets.QMessageBox.warning(self, "Exit", 
                   "The current album has not been saved.  Realy exit?", 
                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No):
            event.ignore()
            return

        # Prompt if there are background operations in progress.
        if 0 != self._backgroundCount:
            prompt_dialog = QtWidgets.QMessageBox(self)
            prompt_dialog.setWindowTitle("Exit")
            prompt_dialog.setIcon(QtWidgets.QMessageBox.Warning)
            prompt_dialog.setText("There is an operation in progress.  Wait for it to complete, " \
                                  "or exit anyway?")
            wait_button = prompt_dialog.addButton("Wait", QtWidgets.QMessageBox.ApplyRole)
            prompt_dialog.addButton("Exit", QtWidgets.QMessageBox.DestructiveRole)
            prompt_dialog.setDefaultButton(wait_button)
            prompt_dialog.setEscapeButton(wait_button)
            prompt_dialog.exec_()
            if wait_button is prompt_dialog.clickedButton():
                # Disable UI controls, except the Cancel button.
                for child in self.findChildren(QtWidgets.QWidget):
                    if child is not self.cancelButton and child is not self.progressBar \
                       and None is child.findChild(QtWidgets.QPushButton, "cancelButton"):
                        child.setEnabled(False)

                # Post a background task to exit after everything else completes.
                # Don't register the task so that it cannot be cancelled.
                self._backgroundInit(0)
                self._threads.submit(self._bgExit, self._backgroundTasks)
                self._backgroundStart([])
                event.ignore()
                return
            else:
                self._cancelBackgroundTasks()

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

    def _addPhotosHandler(self):
        """Prompt the user for photos to add to the album, then load 
        them."""
        sender = self.sender()
        if self._addPhotosFiles is sender:
            # Browse for photos
            file_names = QtWidgets.QFileDialog.getOpenFileNames(self, "Select photos", 
                                                                self._config.photoDir, 
                                                                self.FILTER_IMAGES)
            assert (2 == len(file_names)) and (self.FILTER_IMAGES == file_names[1])
            file_names = file_names[0]
            self._addPhotoFiles([(name, os.path.basename(name)) for name in file_names])
            if 0 < len(file_names):
                self._config.photoDir = os.path.dirname(file_names[len(file_names)-1])
        elif self._addPhotosGthumb3 is sender:
            # Add a gThumb 3 catalog
            catalog_file_name = QtWidgets.QFileDialog.getOpenFileName(self, "Select catalog", 
                                                                      self._config.gthumb3Dir, 
                                                                      self.FILTER_GTHUMB3_CATALOGS)
            assert (2 == len(catalog_file_name)) \
                and (self.FILTER_GTHUMB3_CATALOGS == catalog_file_name[1])
            catalog_file_name = catalog_file_name[0]
            # The QT documentation says that getOpenFileName returns a null string on cancel.  But 
            # it returns an empty string here.  Maybe that's a PyQt bug?
            if "" != catalog_file_name:
                tree = xml.etree.ElementTree.parse(catalog_file_name)
                # Files appear in arbitrary order in a gThumb 3 catalog file.
                # I assume that the display order is the names sorted alphabetically.
                if "1.0" == tree.getroot().get("version"):
                    filenames = sorted(
                            [QtCore.QUrl(urllib.parse.unquote(elmt.attrib["uri"])).toLocalFile() 
                             for elmt in tree.getroot().iter("file")])
                    self._addPhotoFiles([(name, os.path.basename(name)) for name in filenames])
                    self._config.gthumb3Dir = os.path.dirname(catalog_file_name)
                else:
                    QtWidgets.QMessageBox.warning(self, Config.PROGRAM_NAME, 
                                              "Unsupported gThumb catalog version", 
                                              QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)
        else:
            print("ERROR: unknown item selected in 'Add Photos' control")

    def _addPhotoFiles(self, filenames, dirtying=True):
        """Start background tasks to load a list of photos."""
        if 0 < len(filenames):
            self._backgroundInit(len(filenames))
            tasks = []
            task = None
            for (path, name) in filenames:
                task = self._threads.submit(self._bgAddPhoto, path, name, task, dirtying)
                task.photoName = path
                tasks.append(task)
            task = self._threads.submit(functools.partial(handle_exceptions, 
                                                          self._bgAddPhotoComplete), tasks)
            self._backgroundStart(tasks+[task])

    def _removePhotosHandler(self):
        """Remove the currently selected photos from the album."""
        items = self.photosList.selectedItems()
        if 0 < len(items):
            # Clear the selection so that I donn't need to update the selection and make callbacks 
            # with every deletion, which takes a while.
            self.photosList.clearSelection()

            # I need to remove the photo from the list on foreground thread, because the list is 
            # owned by the GUI.  I need to close the Photo object on a background thread, because 
            # that's I/O.
            self._backgroundInit(len(items))
            tasks = []
            task = None
            for item in items:
                photo = self.photosList.takeItem(self.photosList.indexFromItem(item).row())
                task = self._threads.submit(self._bgRemovePhoto, photo)
                tasks.append(task)
            task = self._threads.submit(functools.partial(handle_exceptions, 
                                                          self._bgRemovePhotosComplete), tasks)
            self._backgroundStart(tasks+[task])
            if 0 == self.photosList.count():
                self.generateAlbumButton.setVisible(False)
            self._dirty = True

    def _addPhoto(self, photo, dirtying):
        """Add a photo that has been loaded to the album."""
        self.photosList.addItem(photo)
        self.generateAlbumButton.setVisible(True)
        if dirtying:
            self._dirty = True

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
        QtWidgets.QMessageBox.warning(self, Config.PROGRAM_NAME, err, QtWidgets.QMessageBox.Ok, 
                                      QtWidgets.QMessageBox.Ok)

    def _incProgress(self):
        """Increment the progress bar counter."""
        self.progressBar.setValue(self.progressBar.value() + 1)

    def _backgroundInit(self, steps):
        """Initialize the progress bar for a background action.  This 
        must occur before any background tasks can run."""
        self._backgroundCount += 1
        if 1 == self._backgroundCount:
            self._backgroundTasks = []
            self.generateAlbumButton.setVisible(False)
            self.progressBar.setMaximum(steps)
            self.progressBar.setValue(0)
        else:
            self.progressBar.setMaximum(self.progressBar.maximum() + steps)

    def _backgroundStart(self, tasks):
        """Show the cancellation UI.  Don't do this until after the 
        background tasks are registered so that there's something to 
        cancel."""
        self._backgroundTasks.extend(tasks)
        self.progressBar.setVisible(True)
        self.cancelButton.setVisible(True)

    def _backgroundComplete(self, force):
        """Dismiss the cancellation UI."""
        if True is force:
            assert 0 <= self._backgroundCount
            self._backgroundCount = 0
        else:
            assert 0 < self._backgroundCount
            self._backgroundCount -= 1
        if True is force or 0 == self._backgroundCount:
            self.cancelButton.setVisible(False)
            self.progressBar.setVisible(False)
            self._backgroundTasks = None
            if 0 < self.photosList.count():
                self.generateAlbumButton.setVisible(True)

    def _bgAddPhoto(self, path, name, prev_task, dirtying):
        """Background task to load a photo and signal the UI to add it 
        to the album when done."""
        photo = PhotoFile(path, name, self._config)
        photo.addRef()
        # Wait for the previous photo to be loaded so that photos are added to the list in the 
        # correct order.
        if None is not prev_task:
            concurrent.futures.wait([prev_task])
        self._addPhotoSignal.emit(photo, dirtying)
        self._incProgressSignal.emit()

    def _bgAddPhotoComplete(self, tasks):
        """Background task to display any errors encountered while 
        loading photos, prompt the user to rename any photos with non-
        unique names, and update the lists of available properties and 
        captions."""
        # Wait for the addPhoto tasks to complete.
        (done, not_done) = concurrent.futures.wait(tasks)
        assert 0 == len(not_done)

        # Display any error messages and find any files that need to be renamed
        errors = []
        rename_photos = []
        for task in done:
            try:
                task.result()
            except FileNotFoundError as exc:
                # Either exiftool or the photo was missing.
                if "exiftool" == exc.filename:
                    errors.append("Error executing 'exiftool'.  Is it installed?")
                else:
                    errors.append("Error opening photo " + exc.filename)
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

        # Re-enable any disabled buttons
        self._backgroundCompleteSignal.emit(False)

    def _bgRemovePhoto(self, photo):
        """Background task to clean up after removing a photo."""
        photo.release()
        self._incProgressSignal.emit()

    def _bgRemovePhotosComplete(self, tasks):
        """Background task to perform clean-up after removing photos."""
        # Wait for the removePhoto tasks to complete.
        not_done = concurrent.futures.wait(tasks)[1]
        assert 0 == len(not_done)

        # Update the available properties and captions
        self.showAllPropertiesFlag.stateChanged.emit(0)
        self.showAllCaptionsFlag.stateChanged.emit(0)

        # Re-enable any disabled buttons
        self._backgroundCompleteSignal.emit(False)

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
            self._dirty = True

    def _removeCaptionsHandler(self):
        """Remove the selected caption fields from the album captions."""
        for item in self.captionsList.selectedItems():
            # removeItemWidget() doesn't seem to work
            self.captionsList.takeItem(self.captionsList.indexFromItem(item).row())
            self._dirty = True

    def _addPropertyHandler(self):
        """Add the selected property field to the album properties."""
        if 0 == len(self.propertiesList.findItems(self.sender().text(), 
                                                  QtCore.Qt.MatchFixedString)):
            self.propertiesList.addItem(self.sender().text())
            self._dirty = True

    def _removePropertiesHandler(self):
        """Remove the selected properties fields from the album 
        properties."""
        for item in self.propertiesList.selectedItems():
            # removeItemWidget() doesn't seem to work
            self.propertiesList.takeItem(self.propertiesList.indexFromItem(item).row())
            self._dirty = True

    def _generateAlbum(self):
        """Save an album.  Prompt the user for a file name, then spawn 
        background tasks to generate album and photo JSON, thumbnails, 
        and down-scaled photos.  """
        # Get the output file name
        # Default to the file name of the current album (if it exists).  Do not prompt for 
        # overwrite when re-saving.  QFileDialog can't do that natively, so we implement that logic 
        # here.  Note that it's still vulerable to races: a file that doesn't exist now might exist 
        # when we try to write to it.
        selected = self._config.outputDir
        if None != self._currentAlbumFileName:
            selected = self._currentAlbumFileName
        album_file_name = None
        while True:
            album_file_name = QtWidgets.QFileDialog.getSaveFileName(self, "Album File", 
                                                selected, self.FILTER_ALBUMS, 
                                                options=QtWidgets.QFileDialog.DontConfirmOverwrite)
            assert 2 == len(album_file_name)
            album_file_name = album_file_name[0]
            if self._currentAlbumFileName == album_file_name \
               or not os.path.isfile(album_file_name) \
               or QtWidgets.QMessageBox.Yes == QtWidgets.QMessageBox.warning(self, "Album File", 
                   self.tr("%s already exists.\nDo you want to replace it?") % (album_file_name), 
                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No):
                break
            selected = album_file_name

        if "" != album_file_name:
            album_dir_name = os.path.dirname(album_file_name)

            album = self._saveUIData()
            album["metadataDir"] = urllib.parse.quote(Config.METADATA_DIR + "/")
            album["title"] = self.titleText.toPlainText()
            album["description"] = self.descriptionText.toPlainText()
            album["photos"] = \
                [self.photosList.item(i).getAlbumJSON() for i in range(0, self.photosList.count())]

            # To prevent the output directory from being changed while generating files, we do the 
            # following:
            #  1. Create a secure temporary directory.
            #  2. Open the output directory.  Get its file descriptor.
            #  3. Construct the /proc/<pid>/fd/<fd> path to the directory using the file 
            #     descriptor.
            #  4. Create a symlink from the temporary directory to the /proc path.  The link's name 
            #     is unique but predictable; that's ok because the directory is secure.
            #  5. Use the symlink as the path when creating files.

            self._backgroundInit(3 * self.photosList.count() + 5)
            tasks = []
            directories = DirectoryHandleList()

            # Create the output directories.
            # We read and write directories from different threads, but there's no race 
            # because the read tasks are blocked until after the write task completes.
            album_dir_task = self._threads.submit(self._bgCreateOutputDirectory, album_dir_name, 
                                                  directories, "album")
            tasks.append(album_dir_task)
            metadata_dir_task = None
            if 0 != len(Config.METADATA_DIR):
                metadata_dir_task = self._threads.submit(self._bgCreateOutputDirectory, 
                                                         os.path.join(album_dir_name, 
                                                                      Config.METADATA_DIR), 
                                                         directories, "metadata")
                tasks.append(metadata_dir_task)
            photo_dir_task = None
            if 0 != len(Config.PHOTO_DIR):
                photo_dir_task = self._threads.submit(self._bgCreateOutputDirectory, 
                                                      os.path.join(album_dir_name, 
                                                                   Config.PHOTO_DIR), 
                                                      directories, "photos")
                tasks.append(photo_dir_task)
            thumbnail_dir_task = None
            if 0 != len(Config.THUMBNAIL_DIR):
                thumbnail_dir_task = self._threads.submit(self._bgCreateOutputDirectory, 
                                                          os.path.join(album_dir_name, 
                                                                       Config.THUMBNAIL_DIR), 
                                                          directories, "thumbnails")
                tasks.append(thumbnail_dir_task)

            # Create the album JSON file
            tasks.append(self._threads.submit(self._bgGenerateAlbum, album, 
                                              lambda: os.path.join(
                                                            directories.getPath("album"), 
                                                            os.path.basename(album_file_name)), 
                                              album_dir_task))

            # Create the metadata, thumbnail, and image for each photo.
            count = self.photosList.count()
            if 0 < count:
                captions = album["captionFields"]
                properties = album["propertyFields"]
                for i in range(0, count):
                    photo = self.photosList.item(i)
                    # In Python 3.4, I might be able to use functools.partialmethod to create a 
                    # generic wrapper that calls self._incProgressSignal.emit() after an arbitrary 
                    # method call, rather than needing to write wrappers for every method call.
                    task = self._threads.submit(self._bgGeneratePhotoJSON, photo, 
                                                lambda: directories.getPath("metadata"), 
                                                album["photoResolution"][0], 
                                                album["photoResolution"][1], captions, properties, 
                                                metadata_dir_task)
                    photo.addRef()
                    task.photoName = photo.getPath()
                    tasks.append(task)
                    task = self._threads.submit(self._bgGeneratePhoto, photo, 
                                                lambda: directories.getPath("photos"), 
                                                album["photoResolution"][0], 
                                                album["photoResolution"][1], 
                                                self._config.photoQuality, photo_dir_task)
                    photo.addRef()
                    task.photoName = photo.getPath()
                    tasks.append(task)
                    task = self._threads.submit(self._bgGenerateThumbnail, photo, 
                                                lambda: directories.getPath("thumbnails"), 
                                                Config.THUMB_WIDTH, Config.THUMB_HEIGHT, 
                                                Config.THUMB_QUALITY, thumbnail_dir_task)
                    photo.addRef()
                    task.photoName = photo.getPath()
                    tasks.append(task)

            task = self._threads.submit(functools.partial(handle_exceptions, 
                                                          self._bgTasksComplete), 
                                        tasks, directories, "generating the album", cleansing=True)
            self._backgroundStart(tasks+[task])

            self._config.outputDir = album_dir_name
            self._currentAlbumFileName = album_file_name
            self.setWindowTitle(Config.PROGRAM_NAME + ": " + os.path.basename(album_file_name))

    def _bgCreateOutputDirectory(self, dir_path, directories, name):
        """Background task to create a directory and link to it from 
        the temporary directory."""
        ensure_directory(dir_path)
        dir_fd = os.open(dir_path, os.O_RDONLY)
        directories.add(name, dir_fd)
        self._incProgressSignal.emit()

    def _bgGenerateAlbum(self, album_data, get_album_file_name, dir_creation_task):
        """Background task to generate an album JSON file."""
        if None is not dir_creation_task:
            concurrent.futures.wait([dir_creation_task])
        Album.save(get_album_file_name(), album_data)
        self._incProgressSignal.emit()

    def _bgTasksComplete(self, tasks, directories, message, cleansing=False):
        """Background task to display any errors encountered while 
        executing background tasks and clean up any file descriptors 
        and links that were needed by the background tasks."""
        # Wait for the tasks to complete.
        (done, not_done) = concurrent.futures.wait(tasks)
        assert 0 == len(not_done)

        # Close any file descriptors.  Ignore errors.
        directories.closeAll()

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
            except (SaveError) as exc:
                errors.append(str(exc))
            except:
                (exc_type, exc_value, exc_traceback) = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                errors.append(str(exc_type) + ": " + str(exc_value))
        if 0 != len(errors):
            self._showErrorSignal.emit("%d errors were encountered while %s:\n" % 
                                       (len(errors), message) + "\n".join(errors))

        # Dismiss the cancellation UI
        self._backgroundCompleteSignal.emit(False)

        # Mark the document as no longer dirty.
        if cleansing:
            self._dirtySignal.emit(False)

    def _bgGeneratePhotoJSON(self, photo, get_out_dir_name, width, height, captions, properties, 
                             dir_creation_task):
        """Background task to generate a photo JSON file."""
        # Wait for the directory to be created, then generate the photo JSON
        if None is not dir_creation_task:
            concurrent.futures.wait([dir_creation_task])
        photo.generateJSON(get_out_dir_name(), width, height, captions, properties)
        photo.release()
        self._incProgressSignal.emit()

    def _bgGeneratePhoto(self, photo, get_out_dir_name, width, height, quality, dir_creation_task):
        """Background task to generate a down-scaled photo."""
        # Wait for the directory to be created, then generate the photo
        if None is not dir_creation_task:
            concurrent.futures.wait([dir_creation_task])
        photo.generatePhoto(get_out_dir_name(), width, height, quality)
        photo.release()
        self._incProgressSignal.emit()

    def _bgGenerateThumbnail(self, photo, get_out_dir_name, width, height, quality, 
                             dir_creation_task):
        """Background task to generate a photo thumbnail."""
        # Wait for the directory to be created, then generate the thumbnail
        if None is not dir_creation_task:
            concurrent.futures.wait([dir_creation_task])
        photo.generateThumbnail(get_out_dir_name(), width, height, quality)
        photo.release()
        self._incProgressSignal.emit()

    def _closeAlbum(self, use_defaults):
        """Clear the current album data."""
        # Clear the selected photos.  I can't just call clear() because there's cleanup to do.
        self.photosList.selectAll()
        self._removePhotosHandler()

        # Clear selections and text fields.  Restore defaults if available.
        if use_defaults and None is not self._config.uiData:
            self._restoreUIData(self._config.uiData)
        else:
            self.captionsList.clear()
            self.propertiesList.clear()
            self.footerText.setPlainText(None)
            self.photoSizeButton.setCurrentIndex(0)
        self.titleText.setPlainText(None)
        self.descriptionText.setPlainText(None)

        self._currentAlbumFileName = None
        self.setWindowTitle(Config.PROGRAM_NAME)
        self.generateAlbumButton.setVisible(False)
        self._dirty = False

    def _newAlbum(self):
        """Create a new album."""
        # Prompt if the album is dirty.
        if not self._dirty or 0 == self.photosList.count() \
           or QtWidgets.QMessageBox.Yes == QtWidgets.QMessageBox.warning(self, "New Album", 
                   "The current album has not been saved.  Realy discard it?", 
                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No):
            self._closeAlbum(use_defaults=True)

    def _openAlbum(self):
        """Prompt the user for an album JSON file to load then spawn a 
        background task to load it."""
        # Prompt if the album is dirty.
        if not self._dirty or 0 == self.photosList.count() \
           or QtWidgets.QMessageBox.Yes == QtWidgets.QMessageBox.warning(self, "Open Album", 
                  "The current album has not been saved.  Realy discard it?", 
                  QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No):

            album_file_name = QtWidgets.QFileDialog.getOpenFileName(self, "Select album", 
                                                                    self._config.outputDir, 
                                                                    self.tr(self.FILTER_ALBUMS))
            # The QT documentation says that getOpenFileName returns a null string on cancel.  But 
            # it returns an empty string here.  Maybe that's a PyQt bug?
            assert 2 == len(album_file_name)
            album_file_name = album_file_name[0]
            if "" != album_file_name:
                self._closeAlbum(use_defaults=False)
                # Load the file in a background thread.
                self._backgroundInit(1)
                task = self._threads.submit(functools.partial(handle_exceptions, 
                                                              self._bgLoadAlbum), album_file_name)
                self._backgroundStart([task])

    def _bgLoadAlbum(self, album_file_name):
        """Background task to open and parse an album JSON file."""
        try:
            data = Album.load(album_file_name)
            # Call back to the foreground to populate the UI.
            self._setAlbumDataSignal.emit(album_file_name, data)
        except (OSError) as exc:
            self._showErrorSignal.emit("Error reading '%s': %s." % 
                                       (os.path.basename(album_file_name)), str(exc))
        except (ParseError) as exc:
            self._showErrorSignal.emit("Error loading an album from '%s': %s" % 
                                       (os.path.basename(album_file_name)), str(exc))
        self._backgroundCompleteSignal.emit(False)

    def _setAlbumData(self, album_file_name, data):
        """Pushes data from a loaded album JSON file into the UI."""
        try:
            self._restoreUIData(data, require_fields=True)
            self.titleText.setPlainText(data["title"])
            self.descriptionText.setPlainText(data["description"])
            photos = []
            for photo in data["photos"]:
                path = urllib.parse.unquote(photo["path"])
                photos.append((os.path.expanduser(path), os.path.basename(path)))
            self._addPhotoFiles(photos, dirtying=False)
            self._currentAlbumFileName = album_file_name
            self.setWindowTitle(Config.PROGRAM_NAME + ": " + os.path.basename(album_file_name))
            self._dirty = False
        except KeyError:
            QtWidgets.QMessageBox.warning(None, Config.PROGRAM_NAME, 
                                          "Unable to load an album from '%s'." % 
                                          (os.path.basename(album_file_name)), 
                                          QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)

    def _installTemplate(self):
        """Install the photo album template files.  Prompt the user for 
        a directory, then copy the files over on background threads."""
        # Get the destination directory
        # Using the Qt directory chooser to work around bug 2014-06-06_001.
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Album directory", 
                                                   self._config.outputDir, 
                                                   options=QtWidgets.QFileDialog.ShowDirsOnly
                                                       | QtWidgets.QFileDialog.DontUseNativeDialog)

        if "" != out_dir:
            self._backgroundInit(len(Config.TEMPLATE_FILE_NAMES) + 1)
            tasks = []
            directories = DirectoryHandleList()

            # Create the directory.
            album_dir_task = self._threads.submit(self._bgCreateOutputDirectory, out_dir, 
                                                  directories, "album")
            tasks.append(album_dir_task)

            # Spawn background tasks to do the copying.
            for name in Config.TEMPLATE_FILE_NAMES:
                tasks.append(self._threads.submit(self._bgCopyFile, os.path.join(DATA_PATH, name), 
                                                  lambda filename=name: os.path.join(
                                                          directories.getPath("album"), filename), 
                                                  album_dir_task))

            task = self._threads.submit(functools.partial(handle_exceptions, 
                                                          self._bgTasksComplete), 
                                        tasks, directories, "installing the template")
            self._backgroundStart(tasks+[task])

    def _bgCopyFile(self, source, get_destination, dir_creation_task):
        """Background task to copy a file."""
        # Wait for the directory to be created, then copy the file
        if None is not dir_creation_task:
            concurrent.futures.wait([dir_creation_task])
        shutil.copyfile(source, get_destination())
        self._incProgressSignal.emit()

    def _cancelBackgroundTasks(self):
        """Attempt to cancel any pending background tasks."""
        if None is not self._backgroundTasks:
            for task in reversed(self._backgroundTasks):
                task.cancel()
        concurrent.futures.wait(self._backgroundTasks)
        self._backgroundComplete(True)

    def _renamePhotos(self, photo_names):
        """Prompt the user to rename photos that share names with other 
        photos that have already been loaded, then attempt to load them 
        again using the new names."""
        prompt_dialog = QtWidgets.QMessageBox(self)
        prompt_dialog.setIcon(QtWidgets.QMessageBox.Question)
        rename_button = prompt_dialog.addButton("Rename...", QtWidgets.QMessageBox.YesRole)
        prompt_dialog.addButton("Remove", QtWidgets.QMessageBox.NoRole)

        # Get new names for the files
        new_names = []
        for photo_name in photo_names:
            prompt_dialog.setText("There is already a photo with the name %s in the album.  " \
                                  "Would you like to rename or remove the new one?" % (photo_name))
            prompt_dialog.exec_()
            if rename_button is prompt_dialog.clickedButton():
                # It seems that if I try to re-use the QFileDialog, changing the selected file has 
                # no effect.
                file_dialog = QtWidgets.QFileDialog(self, "New photo name", 
                                                    self._config.tempDir.name, 
                                                    self.FILTER_IMAGES)
                file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
                file_dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
                # The PhotoFile class won't let the user overwrite anything, but with overwrite 
                # confirmations on, QFileDialog prompts to overwrite the directory if a user hits 
                # "Save" with nothing selected.  Disabling confirmation avoids this.
                file_dialog.setOption(QtWidgets.QFileDialog.DontConfirmOverwrite)
                file_dialog.selectFile(os.path.basename(photo_name))
                file_dialog.exec_()
                if 0 < len(file_dialog.selectedFiles()):
                    assert 1 == len(file_dialog.selectedFiles())
                    new_file_name = file_dialog.selectedFiles()[0]
                    new_names.append((photo_name, os.path.basename(new_file_name)))

        # Spawn background tasks to load the files using the new names.
        self._addPhotoFiles(new_names)

    def _about(self):
        """Show the help dialog."""
        dialog = QtWidgets.QDialog(self)
        dialog.ui = Ui_AboutDialog()
        dialog.ui.setupUi(dialog)
        dialog.ui.closeButton.clicked.connect(dialog.close)
        dialog.show()


def main():
    """Main."""
    app = QtWidgets.QApplication(sys.argv)

    # Check that the Python version is at least 3.3, that we're on an OS with /proc/<pid>/fd/<fd>, 
    # and that exiftool and convert are available.  Error out if not.
    if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 3):
        QtWidgets.QMessageBox.critical(None, Config.PROGRAM_NAME, 
                                       "This program requires Python 3.3 or newer.", 
                                       QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)
        sys.exit(1)
    try:
        with open("/proc/%d/fd/0" % (os.getpid())) as fd:
            pass
    except IOError:
        QtWidgets.QMessageBox.critical(None, Config.PROGRAM_NAME, 
                                       "This program currently only runs on Linux.", 
                                       QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)
        sys.exit(1)
    try:
        subprocess.check_call(["exiftool", "-ver"], stdout=subprocess.DEVNULL, timeout=1)
    except (IOError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        QtWidgets.QMessageBox.critical(None, Config.PROGRAM_NAME, 
                                   "This program requires that 'exiftool' be available in your " \
                                   "PATH.", QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)
        sys.exit(1)
    try:
        subprocess.check_call(["convert", "--version"], stdout=subprocess.DEVNULL, timeout=1)
    except (IOError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        QtWidgets.QMessageBox.critical(None, Config.PROGRAM_NAME, "This program requires that " \
                                  "'convert' from the 'ImageMagick' package be available in " \
                                  "your PATH.", QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)
        sys.exit(1)

    with Config() as config:
        wnd = DyphalUI(config)
        wnd.show()
        sys.exit(app.exec_())


if __name__ == '__main__':
    main()
