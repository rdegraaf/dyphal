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
            count = None # Guard against addRef() being called again.
        return count

    def _dispose(self):
        """Dispose of resources held by the derived class."""
        raise NotImplementedError()


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


