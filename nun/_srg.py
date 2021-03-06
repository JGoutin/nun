"""Local storage"""
from hashlib import blake2b
from json import load, loads, dump, dumps
from os import listdir, utime, remove, chmod
from os.path import join, getmtime
from time import time

from nun._cfg import CACHE_DIR, CONFIG_DIR, APP_NAME

_CACHE_LONG_EXPIRY = 172800
_CACHE_SHORT_EXPIRY = 60
_STORE_FILE = join(CONFIG_DIR, "store")


def _hash_name(name):
    """
    Convert name to hashed name.

    Args:
        name (str): name.

    Returns:
        str: Hashed name.
    """
    return blake2b(name.encode(), digest_size=32).hexdigest()


def clear_cache():
    """
    Clear expired cache files.
    """
    expiry = _get_expiry()
    for cached_name in listdir(CACHE_DIR):
        path = join(CACHE_DIR, cached_name)
        if getmtime(path) < expiry[cached_name[-1]]:
            remove(path)
            continue


def _get_expiry():
    """
    Get expiry timestamps.

    Returns:
        dict: Expiry for both short and long modes.
    """
    current_time = time()
    return {
        "s": current_time - _CACHE_SHORT_EXPIRY,
        "l": current_time - _CACHE_LONG_EXPIRY,
    }


def get_cache(name, recursive=False):
    """
    Get an object from disk cache.

    Args:
        name (str): Cache name.
        recursive (bool): If True, recursively search for cached values starting by
        various "name" prefixes.

    Returns:
        dict or list or None: object, None if object is not cached.
    """
    # Create list of names to search
    if recursive:
        names = []
        while name and not name.endswith("|"):
            names.append(name)
            name = name[:-1]
        names.append(name)

    else:
        names = (name,)

    # Get cached value if not expired
    expiry = _get_expiry()
    for hashed_name in (_hash_name(name) for name in names):
        for mode in ("s", "l"):
            path = join(CACHE_DIR, hashed_name + mode)

            try:
                timestamp = getmtime(path)
            except FileNotFoundError:
                # Not cached
                continue

            if timestamp < expiry[mode]:
                # Expired, deleted
                remove(path)
                continue

            if mode == "l":
                # In long cache mode, reset expiry delay
                utime(path)

            # Retrieve cached data
            with open(path, "rt") as file:
                return loads(file.read())


def set_cache(name, obj, long=False):
    """
    Add an object to disk cache.

    Args:
        name (str): Cache name.
        obj (dict or list): Object to cache.
        long (bool): If true, enable "long cache". Long cache have a far greater
            expiration delay that is reset on access. This is useful to store data that
            will likely not change.
    """
    path = join(CACHE_DIR, _hash_name(name) + ("l" if long else "s"))
    with open(path, "wt") as file:
        file.write(dumps(obj))


def get_secret(name):
    """
    Get a secret from OS keyring.

    Args:
        name (str): Secret name.

    Returns:
        str or None: Secret value.
    """
    key = _hash_name(name)

    # Use OS keyring if possible
    try:
        from keyring import get_password

        return get_password(APP_NAME, key)

    # Use local file if not in configuration directory
    except ImportError:
        try:
            with open(_STORE_FILE, "rt") as store_json:
                return load(store_json).get(key)
        except FileNotFoundError:
            return


def set_secret(name, value):
    """
    Set a secret in OS keyring.

    Args:
        name (str): Secret name.
        value (str): Secret value.
    """
    key = _hash_name(name)

    # Use OS keyring if possible
    try:
        from keyring import set_password

        set_password(APP_NAME, key, value)

    # Use local file if not in configuration directory
    except ImportError:
        try:
            with open(_STORE_FILE, "rt") as store_json:
                store = load(store_json)
        except FileNotFoundError:
            store = dict()

        store[key] = value
        with open(_STORE_FILE, "wt") as store_json:
            dump(store, store_json)
        chmod(_STORE_FILE, 0o600)
        return
