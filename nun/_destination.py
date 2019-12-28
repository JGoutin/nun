# coding=utf-8
"""
Destination
"""
from hashlib import blake2b
from os import rename, utime, remove
from os.path import isfile
from shutil import copystat
from time import time

from nun._exceptions import CancelException

BUFFER_SIZE = 65536


def _remove_existing(path):
    """
    Remove a local file, ignoring error if not existing.

    Args:
        path (path-like object): File path.
    """
    try:
        remove(path)
    except FileNotFoundError:
        pass


class Destination:
    """
    Destination file on the local filesystem.

    Args:
        path (str): Destination path.
        mtime (int or float): Modification time.
        force (bool): Replace destination if exists and modified by user.
    """
    __slots__ = ('_path', '_hash_cur', '_hash_new', '_hash_old', '_path_part',
                 '_update', '_path_bak', '_mtime', '_force', '_hash_obj',
                 '_file_obj')

    def __init__(self, path, mtime=None, force=False):
        # TODO:
        #  - Use SpooledTemporaryFile and freeze it on drive
        #    when self._update is True
        #  - Set ".part.nun" mode to 600

        self._path = path
        self._path_part = None
        self._path_bak = None
        self._file_obj = None

        self._hash_cur = None
        self._hash_new = None
        self._hash_old = ''  # None  # TODO: set from database

        self._update = False
        self._mtime = mtime
        self._force = force

        # Not update required if has changed since previously installed
        if (not self._force and self._hash_old and
                self._hash_old != self._check_current()):
            # Does not replace file if modified
            self.cancel(f'Destination "{path}" was modified since installation')

        # Initialize the write sequence
        self._path_part = self._path + '.part.nun'
        self._file_obj = open(self._path_part, 'wb')
        self._hash_obj = blake2b()

    def __del__(self):
        self.cancel()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    @property
    def path(self):
        """
        Destination path

        Returns:
            str: Destination path.
        """
        return self._path

    def _check_current(self):
        """
        Check if destination already exists and hash its content.

        Returns:
            str: Hash if file exists or empty string if not.
        """
        if self._hash_cur is None:
            try:
                h = blake2b()
                with open(self._path, 'rb') as file:
                    while True:
                        chunk = file.read(BUFFER_SIZE)
                        if not chunk:
                            break
                        h.update(chunk)
                self._hash_cur = h.hexdigest()

            except FileNotFoundError:
                self._hash_cur = ''

        return self._hash_cur

    def write(self, data):
        """
        Write the new content into a file.

        Args:
            data (file-like object or bytes-like object): Data to write.
        """
        # Content is a file-like object to fully copy to the destination
        if hasattr(data, 'read'):
            update_hash = self._hash_obj.update
            write = self._file_obj.write
            read = data.read
            while True:
                chunk = read(BUFFER_SIZE)
                if not chunk:
                    break
                update_hash(chunk)
                write(chunk)

            self.close()

        # Content are bytes to append to destination
        else:
            self._hash_obj.update(data)
            self._file_obj.write(data)

    def close(self):
        """
        Close pending write of data and check if update is required or not based
        on hash comparison.
        """
        if self._file_obj is None:
            return

        self._file_obj.close()
        self._file_obj = None

        # Get new content hash
        self._hash_new = self._hash_obj.hexdigest()
        self._hash_obj = None

        # No update required if content has not changed
        if self._hash_old == self._hash_new:
            self.cancel()
            return

        # No update required if exists but not installed by the application
        elif (not self._force and not self._hash_old and
              self._check_current()):
            if self._hash_new != self._check_current():
                self.cancel(f'Destination "{self._path}" already exists with a '
                            'different content.')
            else:
                self.cancel()
            return

        # Update required in any other case
        self._update = True

    def move(self, mtime=None):
        """
        Create a back up of the destination if exists and move pending new
        content to the destination.
        """
        if self._update:
            # Back up previous destination
            path_bak = self._path + '.bak.nun'
            try:
                rename(self._path, path_bak)
                self._path_bak = path_bak
            except FileNotFoundError:
                pass

            # Move new content to new destination
            rename(self._path_part, self._path)

            # Update stat based on previous version
            try:
                copystat(path_bak, self._path)
            except FileNotFoundError:
                pass

            # Update modification time
            mtime = mtime or self._mtime
            if mtime is not None:
                utime(self._path, (time(), mtime))
            self._path_part = None

    def clear(self):
        """
        Clear the destination back up.
        """
        if self._path_bak is not None:
            _remove_existing(self._path_bak)
            self._path_bak = None

    def cancel(self, msg=None):
        """
        Cancel any action on the destination.

        Args:
            msg (str): If specified, throw the cancellation at the upper
                level with the specified message.
        """
        if self._file_obj is not None:
            self._file_obj.close()
            self._file_obj = None

        if self._path_part is not None:
            _remove_existing(self._path_part)
            self._path_part = None

        if self._path_bak is not None:
            if isfile(self._path_bak):
                _remove_existing(self._path_part)
                rename(self._path_bak, self._path)
            self._path_bak = None

        if msg:
            raise CancelException()
