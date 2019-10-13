"""Cache management"""
from hashlib import blake2b
from json import loads, dumps
from os import listdir, utime, remove
from os.path import join, getmtime
from time import time

from aiofiles import open as aiopen

from nun._config import CACHE_DIR

_LONG_EXPIRY = 172800
_SHORT_EXPIRY = 60


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
    return {'s': current_time - _SHORT_EXPIRY,
            'l': current_time - _LONG_EXPIRY}


async def get_cache(name, recursive=False):
    """
    Get an object from disk cache.

    Args:
        name (str): Cache name.
        recursive (bool): If True, recursively search for cached values
            starting by various "name" prefixes.

    Returns:
        dict or list or None: object, None if object is not cached.
    """
    # Create list of names to search
    if recursive:
        names = []
        while name and not name.endswith('|'):
            names.append(name)
            name = name[:-1]
        names.append(name)

    else:
        names = name,

    # Get cached value if not expired
    expiry = _get_expiry()
    for hashed_name in (_hash_name(name) for name in names):
        for mode in ('s', 'l'):
            path = join(CACHE_DIR, hashed_name + mode)

            try:
                timestamp = getmtime(path)
            except FileNotFoundError:
                # Not cached
                continue

            if timestamp < expiry[mode]:
                # Expired, deleted
                await remove(path)
                continue

            if mode == 'l':
                # In long cache mode, reset expiry delay
                utime(path)

            # Retrieve cached data
            async with aiopen(path, 'rt') as file:
                return loads(await file.read())


async def set_cache(name, obj, long=False):
    """
    Add an object to disk cache.

    Args:
        name (str): Cache name.
        obj (dict or list): Object to cache.
        long (bool): If true, enable "long cache". Long cache have a
            far greater expiration delay which is reset on access. This is
            useful to store data that will likely not change.
    """
    path = join(CACHE_DIR, _hash_name(name) + ('l' if long else 's'))
    async with aiopen(path, 'wt') as file:
        await file.write(dumps(obj))
