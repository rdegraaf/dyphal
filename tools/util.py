"""Utility functions and classes for DyphalGenerator.
Copyright (c) Rennie deGraaf, 2005-2016.

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

import threading
import os
import sys
import traceback

class Counter(object):
    """An atomic counter."""

    def __init__(self, initval=0):
        """Initialize an atomic counter."""
        self.__lock = threading.Lock()
        self.__val = initval

    def incr(self):
        """Increment an atomic counter and return the result."""
        with self.__lock:
            self.__val += 1
            return self.__val

    def decr(self):
        """Decrement an atomic counter and return the result."""
        with self.__lock:
            self.__val -= 1
            return self.__val

    def value(self):
        """Return the value of an atomic counter."""
        with self.__lock:
            return self.__val


class RefCounted(object):
    """Base class for reference counted objects.

    This class implements COM-style reference counting.  The initial reference 
    count is 0; the caller must call addRef().  When the reference count 
    returns to 0, _dispose() is called; subclasses should override this method. 
    The object isn't actually destroyed because that's up to Python, but 
    subsequent calls to addRef() or release() will raise exceptions.
    """

    def __init__(self, *args, **kwargs):
        """Initialize a RefCounted."""
        # Pass constructor parameters along in case some base class gets inserted that wants them.
        super().__init__(*args, **kwargs)
        self.__refCount = Counter(0)

    def addRef(self):
        """Add a reference."""
        return self.__refCount.incr()

    def release(self):
        """Release a reference and potentially destroy the object."""
        count = self.__refCount.decr()
        assert(0 <= count)
        if 0 >= count:
            self._dispose()
            self.__refCount = None # Guard against addRef() being called again.
        return count

    def _dispose(self):
        """Dispose of resources held by the derived class."""
        raise NotImplementedError()


class DirectoryHandleList(object):
    """Thread-safe name to file descriptor mapping."""

    def __init__(self, *args, **kwargs):
        """Initialize a DirectoryHandleList."""
        self._directories = {}
        self._lock = threading.Lock()

    def add(self, name, fd):
        """Map a name to a file descriptor."""
        with self._lock:
            self._directories[name] = fd

    def getPath(self, name):
        """Retrieve a path to the file descriptor."""
        with self._lock:
            return "/proc/%d/fd/%d" % (os.getpid(), self._directories[name])

    def closeAll(self):
        """Close all file descriptors and remove their mappings."""
        with self._lock:
            for fd in self._directories.values():
                try:
                    os.close(fd)
                except OSError:
                    pass
            self._directories = {}


def handle_exceptions(func, *args, **kwargs):
    """Call a function and log any exceptions that it throws.  Pass 
    'functools.partial(handle_exceptions, func)' to something that 
    expects a callable."""
    try:
        func(*args, **kwargs)
    except:
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        raise


def ensure_directory(name):
    """Ensure that a directory exists."""
    try:
        # This will throw FileExistsError if the permissions are different than expected.
        os.makedirs(name, exist_ok=True)
    except FileExistsError:
        pass


