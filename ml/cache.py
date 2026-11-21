"""Cache helper shared by the models and the API."""

import os
import threading
from functools import wraps


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def cached_on_files(*paths: str):
    """
    Cache a function's result until one of the given files changes. The analyses read the whole
    warehouse (and sometimes fit K-means or Granger tests), so recomputing them for every page view
    would let a handful of visitors keep the server busy. A refreshed warehouse or a retrained model
    changes a file's modified time, which drops the cache automatically.
    """

    def decorator(fn):
        store: dict = {}
        lock = threading.Lock()

        @wraps(fn)
        def wrapper(*args):
            # With no explicit files, the first argument is the warehouse path the function reads.
            files = paths or tuple(a for a in args[:1] if isinstance(a, str))
            key = (args, tuple(_mtime(p) for p in files))
            with lock:
                if key in store:
                    return store[key]
            result = fn(*args)
            with lock:
                if len(store) > 16:
                    store.clear()
                store[key] = result
            return result

        wrapper.cache_clear = store.clear
        return wrapper

    return decorator
