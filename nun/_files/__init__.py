# coding=utf-8
"""Files & packages formats"""
from abc import ABC
from dateutil.parser import parse
from importlib import import_module
from os import fsdecode
from os.path import join, isdir, realpath, dirname, expanduser, isabs, splitext
from pathlib import PurePath

from nun._destination import Destination
from nun._database import DB

#: File types aliases
ALIASES = {
    'tgz': 'tar',
    'tbz': 'tar',
    'tlz': 'tar',
    'txz': 'tar'
}


def create_file(name, url, resource, platform, task_id, file_type=None,
                mtime=None, strip_components=0, revision=None):
    """
    Args:
        name (str): File name.
        url (str): URL.
        resource (nun._platforms.ResourceBase subclass instance): Resource.
        platform (nun._platforms.PlatformBase subclass): platform
        task_id (int): Task ID.
        file_type (str): File type to use if known in advance.
        mtime (int or float): Modification timestamp.
        strip_components (int): strip NUMBER leading components from file
            path when extracting an archive.
        revision (str): File revision.

    Returns:
        nun._files.FileBase subclass instance: File
    """
    # Detect file type based on its extension
    if file_type is None:
        filename, ext = splitext(name.lower())
        if ext in ('.gz', '.bz2', '.lz', '.xz') and filename.endswith('.tar'):
            # Handle the ".tar.<compression>" special case
            file_type = 'tar'
        else:
            file_type = ext.lstrip('.')

        file_type = ALIASES.get(file_type, file_type)

    try:
        cls = import_module(f'nun._files.{file_type}').File
    except ImportError:
        cls = FileBase

    return cls(name, url, resource, platform, task_id, mtime=mtime,
               strip_components=strip_components, revision=revision)


class FileBase(ABC):
    """
    File base.

    Args:
        name (str): File name.
        url (str): URL.
        resource (str): Resource.
        platform (nun._platforms.PlatformBase subclass): platform
        task_id (int): Task ID.
        mtime (int or float or str): Modification time or timestamp.
        strip_components (int): strip NUMBER leading components from file
            path when extracting an archive.
        revision (str): File revision.
    """
    __slots__ = ('_name', '_url', '_resource', '_size', '_task_id',
                 '_size_done', '_done', '_exception', '_mtime', '_revision',
                 '_output', '_trusted', '_platform', '_db_info',
                 '_destinations')

    def __init__(self, name, url, resource, platform, task_id,
                 mtime=None, strip_components=0, revision=None):

        self._name = name
        self._url = url
        self._resource = resource
        self._platform = platform
        self._done = False
        self._exception = None
        self._output = None
        self._strip_components = strip_components
        self._trusted = False
        self._task_id = task_id
        self._db_info = DB.get_file(task_id, name)
        self._revision = self._get_revision(revision)
        self._destinations = None

        if isinstance(mtime, str):
            mtime = parse(mtime).timestamp()
        self._mtime = mtime

        # For progress information
        self._size = 0
        self._size_done = 0

    @property
    def name(self):
        """
        File name.

        Returns:
            str: name.
        """
        return self._name

    @property
    def resource(self):
        """
        File resource

        Returns:
            str: resource.
        """
        return self._resource

    @property
    def size(self):
        """
        File size.

        Returns:
            int: number of bytes.
        """
        return self._size

    @property
    def size_done(self):
        """
        Processed file size.

        Returns:
            int: number of bytes.
        """
        return self._size_done

    @property
    def done(self):
        """
        Operation completed

        Returns:
            bool: True if done.
        """
        return self._done

    @property
    def exception(self):
        """
        Exception that occurred during operation if any.

        Returns:
            None or Exception subclass: Exception.
        """
        return self._exception

    @property
    def destinations(self):
        """
        Destinations IDs.

        Returns:
            None or set of int: Destinations IDs. If None,
                the file and its destinations are unchanged.
        """
        return self._destinations

    def _cancel(self, update, force):
        """
        Return True if cancel the operation.

        Args:
            update (bool): True if it is an update operation.
            force (bool): True if operation is forced to run.

        Returns:
            bool: True if cancelled.
        """
        if (update and not force and self._db_info is not None and
                self._revision == self._db_info.revision):
            self._destinations = True
            return True
        return False

    def _get_revision(self, revision):
        """
        Get a default revision from headers if not specified.

        Args:
            revision (str or None): revision

        Returns:
            str: revision
        """
        if revision is not None:
            return revision

        resp = self._platform.request(self._url, method='HEAD')
        self._platform.exception_handler(
            self._resource, self._name, resp.status_code)
        headers = resp.headers
        etag = headers.get('ETag')
        if etag and not etag.startswith('W/'):
            return etag
        else:
            return headers.get('Last-Modified')

    def set_done_callback(self, future):
        """
        Callback to set the file operation completed.

        Args:
            future (concurrent.futures.Future): Future.
        """
        self._done = True
        self._exception = future.exception()

    def add_size_callback(self, size):
        """
        Callback to update file size completed.

        Args:
            size (int):
        """
        self._size_done += size

    @property
    def file_id(self):
        """
        File ID in database.

        Returns:
            int: File ID.
        """
        return self._db_info['id']

    def _db_update(self, transaction_id, destinations=None):
        """
        Update the file in the database.

        Args:
            destinations (iterable of nun._destination.Destination):
                destinations.
        """
        # Update the file in the database
        file_id = DB.set_file(
            ref_values=self._db_info, transaction_id=transaction_id,
            task_id=self._task_id, name=self._name, revision=self._revision,
            size=self._size)

        # Update destinations in the database
        if destinations:
            self._destinations = set()
            add = self._destinations.add
            kwargs = dict(transaction_id=transaction_id,
                          task_id=self._task_id, file_id=file_id)

            for dest in destinations:
                add(dest.db_update(**kwargs))

    def download(self, output='.', force=False, update=False,
                 transaction_id=None):
        """
        Download the file.

        Args:
            output (path-like object): Destination.
            force (bool): Force update and replace any existing destination even
                if modified by user.
            update (bool): If True, is an update of an already in the database
                entry.
            transaction_id (int): Transaction ID.
        """
        if self._cancel(update, force):
            return

        self._set_output(output)
        path = self._set_path(self._name, strip_components=0)

        # Force strip_components=0 on a single file
        with Destination(path, force=force, task_id=self._task_id) as dest:
            dest.write(self._get())
            dest.move(self._mtime)
            dest.clear()

        self._db_update(transaction_id, (dest,))

    def extract(self, output='.', trusted=False, strip_components=0,
                force=False, update=False, transaction_id=None):
        """
        Extract the file.

        Args:
            output (path-like object): Destination.
            trusted (bool): If True, allow extraction of files outside of the
                output directory. Default to False, because this can be a
                security issue if extracted from an untrusted source.
            strip_components (int): strip NUMBER leading components from file
                path on extraction.
            force (bool): Force update and replace any existing destination even
                if modified by user.
            update (bool): If True, is an update of an already in the database
                entry.
            transaction_id (int): Transaction ID.
        """
        if self._cancel(update, force):
            return

        self._trusted = trusted
        self._set_output(output)
        if strip_components is not 0:
            self._strip_components = strip_components

        # Perform operation sequentially to allow to revert back on error
        destinations = self._extract()

        for dest in destinations:
            dest.move()

        for dest in destinations:
            dest.clear()

        self._db_update(transaction_id, destinations)

    def _extract(self):
        """
        Extract the file.

        Returns:
            list of nun._destination.Destination: destinations
        """
        raise NotImplementedError(f'extracting {self._name} is not supported.')

    def install(self, force=False, update=False, transaction_id=None):
        """
        Install the file.

        Args:
            force (bool): Force update and replace any existing destination even
                if modified by user.
            update (bool): If True, is an update of an already in the database
                entry.
            transaction_id (int): Transaction ID.
        """
        if self._cancel(update, force):
            return

        self._install()
        self._db_update(transaction_id)

    def _install(self):
        """
        Install the file.
        """
        raise NotImplementedError(f'Installing {self._name} is not supported.')

    def _get(self):
        """
        Performs a get request on file URL.

        Returns:
            file-like object: Response content.
        """
        # Perform requests and handle exceptions
        resp = self._platform.request(self._url, stream=True)
        self._platform.exception_handler(
            self._resource, self._name, resp.status_code)

        # Get information from headers
        headers = resp.headers
        self._size = int(headers.get('Content-Length', 0))
        if self._mtime is None:
            try:
                self._mtime = parse(headers['Last-Modified']).timestamp()
            except KeyError:
                pass

        # Update file name if specified
        try:
            content = headers['Content-Disposition'].split('=', 1)
            if content[0].endswith('filename'):
                self._name = content[1]
        except (KeyError, IndexError):
            pass

        # Return response body
        return Body(resp, self)

    def _set_output(self, output):
        """
        Set the output directory.

        Args:
            output (path-like object): output directory.
        """
        self._output = realpath(expanduser(fsdecode(output)))

    def _set_path(self, path, target_is_dir=False,
                  strip_components=None):
        """
        Set final destination path.

        Args:
            path (str): Object path.
            target_is_dir (bool): Target is a directory.
            strip_components (int): strip NUMBER leading components from file
                path.

        Returns:
            str: Destination absolute path.
        """
        # TODO: use PurePath everywhere
        if strip_components is None:
            strip_components = self._strip_components

        if strip_components:
            path = str(PurePath(*PurePath(path).parts[strip_components:]))

        # Ensure path is not outside output directory for untrusted sources
        absolute = isabs(path)
        if not self._trusted and (absolute or path.startswith('..')):
            raise PermissionError(
                f'The "{self._name}" target a destination outside '
                f'of the output directory. If you trust this source, use the '
                f'"trusted" option to allow this behavior.')

        # Returns absolute paths without changes
        elif absolute:
            return path

        if isdir(self._output):
            # Destination is this directory
            if target_is_dir:
                return self._output

            # Destination is a file in this directory
            return join(self._output, path)

        # Parent directory does not exists
        if not isdir(dirname(self._output)):
            raise FileNotFoundError(
                f'Output directory "{dirname(self._output)}" does not exists.')

        # This directory is a new sub-directory
        return self._output


class Body:
    """
    Body file like object

    Args:
        response (requests.Response): Response.
        file (nun._files.FileBase): File.
    """
    __slots__ = ('_response', '_add_size', '_read', '_file')

    def __init__(self, response, file):
        self._response = response
        self._file = file

        # Common functions
        self._add_size = file.add_size_callback
        self._read = self._response.raw.read

    def read(self, size=-1):
        """
        Read body.

        Args:
            size (int):

        Returns:
            bytes: Read data.
        """
        # Read data
        chunk = self._read(None if size == -1 else size, decode_content=True)

        # Update downloaded size
        self._add_size(len(chunk))

        return chunk

    def tell(self):
        """
        Return current read position.

        Returns:
            int: Position.
        """
        return self._file.size_done
