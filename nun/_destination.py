"""
Destination
"""
from asyncio import create_task
from hashlib import blake2b
from os.path import isfile

from aiofiles import open as aiopen

from nun._common import hash_data, remove, rename, BUFFER_SIZE

# TODO: Get from db and update db


class Destination:
    """
    Destination file on the local filesystem.
    """
    __slots__ = ('_path', '_hash_cur', '_hash_new', '_hash_old', '_path_part',
                 '_update', '_path_bak')

    def __init__(self, path):
        self._path = path
        self._path_part = None
        self._path_bak = None
        self._hash_cur = None
        self._hash_new = None
        self._hash_old = None
        self._update = True

    @property
    def path(self):
        """
        Destination path

        Returns:
            str: Destination path.
        """
        return self._path

    async def _check_current(self):
        """
        Check if destination already exists and hash its content.

        Returns:
            str: Hash if file exists or empty string if not.
        """
        if self._hash_cur is None:
            try:
                h = blake2b()
                async with aiopen(self._path, 'rb') as file:
                    while True:
                        chunk = await file.read(BUFFER_SIZE)
                        if not chunk:
                            break
                        await hash_data(chunk, h)
                self._hash_cur = h.hexdigest()

            except FileNotFoundError:
                self._hash_cur = ''

        return self._hash_cur

    async def write(self, content, replace=False):
        """
        Write the pending content in a temporary location to prepare
        destination update or creation. Also hash the content while writing it.

        Args:
            content (async file-like object): Content to write.
            replace (bool): Replace destination if exists and modified by user.
        """
        # TODO: set ".part.nun" mode to 600
        self._path_part = self._path + '.part.nun'
        write_task = None
        hash_task = None
        h = blake2b()

        # TODO: Use SpooledTemporaryFile and freeze it on drive
        #       when self._update is True
        async with aiopen(self._path_part, 'wb') as file:
            while True:
                chunk = await content.read(BUFFER_SIZE)
                if write_task is not None:
                    await write_task
                    await hash_task

                if not chunk:
                    break

                hash_task = create_task(hash_data(chunk, h))
                write_task = create_task(file.write(chunk))

        self._hash_new = h.hexdigest()

        await self._needs_update(replace)
        if not self._update:
            await self.cancel()

    async def _needs_update(self, replace):
        """
        Define if the destination require to be updated or not.

        Args:
            replace (bool): Replace destination if exists and modified by user.

        Returns:
            bool: True if update is required.
        """
        new = self._hash_new
        old = self._hash_old

        if old and old == new:
            # If the content does not changed, no update is required
            self._update = False

        elif not replace:

            cur = await self._check_current()

            if cur and old and old != cur:
                # TODO: Check this before writing "new"
                # The destination was modified by the user and should not be
                # replaced by the application
                # TODO: Warn user / ask user validation
                self._update = False

            elif cur and not old and cur != new:
                # A file already exists that must not be replaced
                # TODO: Warn user / ask user validation
                self._update = False

        self._update = True

    async def move(self):
        """
        Create a back up of the destination if exists and move pending new
        content to the destination.
        """
        if self._update:
            # TODO: Copy file stat + set modified time to resource modified time
            self._path_bak = self._path + '.bak.nun'
            await rename(self._path, self._path_bak)
            await rename(self._path_part, self._path)
            self._path_part = None

    async def clear(self):
        """
        Clear the destination back up.
        """
        if self._path_bak is not None:
            await remove(self._path_bak)
            self._path_bak = None

    async def cancel(self):
        """
        Cancel any action on the destination.
        """
        if self._path_part is not None:
            await remove(self._path_part)
            self._path_part = None

        if self._path_bak is not None:
            if isfile(self._path_bak):
                await remove(self._path_part)
                await rename(self._path_bak, self._path)
            self._path_bak = None
