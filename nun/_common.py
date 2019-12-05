"""Common functions"""
from asyncio.events import get_running_loop
from functools import partial
from os import remove as _remove, rename as _rename

BUFFER_SIZE = 65536


async def run_async(func, *args, **kwargs):
    """
    Run function asynchronously.

    Args:
        func (function):
        args: Function arguments.
        kwargs: Function keyword arguments.

    Returns:
        function result
    """
    return await get_running_loop().run_in_executor(
        None, partial(func, *args, **kwargs))


async def hash_data(data, h):
    """
    Hash data with the Black2 algorithm.

    Args:
        data (bytes-like object): data to hash.
        h (hashlib.hash): Hash object to update.
    """
    await run_async(h.update, data)


async def remove(path):
    """
    Remove a local file, ignoring error if not existing.

    Args:
        path (path-like object): File path.
    """
    try:
        await run_async(_remove, path)
    except FileNotFoundError:
        pass


async def rename(src, dst):
    """
    Move a local file

    Args:
        src (path-like object): Source path.
        dst (path-like object): Destination path.
    """
    await run_async(_rename, src, dst)
