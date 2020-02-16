# coding=utf-8
"""Files & packages formats"""
from abc import ABC
from dateutil.parser import parse
import hashlib
from importlib import import_module
from os import fsdecode
from os.path import join, isdir, realpath, dirname, expanduser, isabs, splitext
from pathlib import PurePath

from nun._destination import Destination

#: File types aliases
ALIASES = {
    'tgz': 'tar',
    'tbz': 'tar',
    'tlz': 'tar',
    'txz': 'tar'
}


def create_file(name, url, resource, file_type=None, mtime=None,
                strip_components=0):
    """
    Args:
        name (str): File name.
        url (str): URL.
        resource (nun._platforms.ResourceBase subclass instance): Resource.
        file_type (str): File type to use if known in advance.
        mtime (int or float): Modification timestamp.
        strip_components (int): strip NUMBER leading components from file
            path when extracting an archive.

    Returns:
        FileBase subclass instance: File
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

    return cls(name, url, resource, mtime=mtime,
               strip_components=strip_components)


class FileBase(ABC):
    """
    File base.

    Args:
        name (str): File name.
        url (str): URL.
        resource (nun._platforms.ResourceBase subclass instance): Resource.
        mtime (int or float or str): Modification time or timestamp.
        strip_components (int): strip NUMBER leading components from file
            path when extracting an archive.
    """
    __slots__ = ('_name', '_url', '_resource', '_request', '_size',
                 '_size_done', '_done', '_exception', '_mtime', '_etag',
                 '_accept_range', '_output', '_trusted', '_status')

    def __init__(self, name, url, resource, mtime=None, strip_components=0):
        self._name = name
        self._url = url
        self._resource = resource
        self._request = self._resource.platform.request
        self._done = False
        self._exception = None
        self._content_type = None
        self._etag = None
        self._accept_range = False
        self._output = None
        self._strip_components = strip_components
        self._trusted = False
        self._status = ''

        if mtime is None:
            mtime = resource.mtime
        if isinstance(mtime, str):
            mtime = parse(mtime).timestamp()
        self._mtime = mtime

        # For progress information
        self._size = 0
        self._size_done = 0

        # File hash, "hash_obj.update" will be used as callback
        # TODO: hash init with hashlib.new, depending the algo to use for
        #       comparison
        self.hash_obj = None

    @property
    def name(self):
        """
        File name.

        Returns:
            str: name.
        """
        return self._name

    @property
    def resource_id(self):
        """
        File resource ID

        Returns:
            str: ID.
        """
        return self._resource.resource_id

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
    def digest(self):
        """
        File digest.

        Returns:
            str: Digest
        """
        if self.hash_obj:
            return self.hash_obj.hexdigest()

    @property
    def status(self):
        """
        File final status.

        Returns:
            str: status
        """
        return self._status

    @property
    def exception(self):
        """
        Exception that occurred during operation if any.

        Returns:
            None or Exception subclass: Exception.
        """
        return self._exception

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

    def download(self, output='.', force=False):
        """
        Download the file.

        Args:
            output (path-like object): Destination.
            force (bool): Replace destination if exists and modified by user.

        Returns:
            list of str: Downloaded files paths.
        """
        self._set_output(output)
        path = self._set_path(self._name, strip_components=0)

        # Force strip_components=0 on a single file
        with Destination(path, force=force) as dest:
            dest.write(self._get())
            dest.move(self._mtime)
            dest.clear()

        self._status = f'downloaded to "{path}"'
        return [dest.path]

    def extract(self, output='.', trusted=False, strip_components=0,
                force=False):
        """
        Extract the file.

        Args:
            output (path-like object): Destination.
            trusted (bool): If True, allow extraction of files outside of the
                output directory. Default to False, because this can be a
                security issue if extracted from an untrusted source.
            strip_components (int): strip NUMBER leading components from file
                path on extraction.
            force (bool): Replace any existing destination even if modified by
                user.

        Returns:
            list of str: Extracted files paths.
        """
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

        self._status = f'extracted to "{self._output}"'
        return [dest.path for dest in destinations]

    def _extract(self):
        """
        Extract the file.

        Returns:
            list of nun._destination.Destination: destinations
        """
        raise NotImplementedError(f'extracting {self._name} is not supported.')

    def install(self):
        """
        Install the file.

        Returns:
            list of str: Installed files paths.
        """
        self._install()
        self._status = 'installed'

    def _install(self):
        """
        Install the file.

        Returns:
            list of str: Installed files paths.
        """
        raise NotImplementedError(f'Installing {self._name} is not supported.')

    def _get(self):
        """
        Performs a get request on file URL.

        Returns:
            file-like object: Response content.
        """
        # TODO:
        #  - Compare ETag and cancel action if identical to previous
        #    ignore absent or weak ETag (starts by "W/")

        # Perform requests and handle exceptions
        resp = self._request(self._url, stream=True)
        self._resource.exception_handler(resp.status_code, self._name)

        # Get information from headers
        headers = resp.headers
        self._size = int(headers.get('Content-Length', 0))

        if self._mtime is None:
            try:
                self._mtime = parse(headers['Last-Modified']).timestamp()
            except KeyError:
                pass

        self._etag = headers.get('ETag')
        self._accept_range = headers.get('Accept-Ranges', 'none') == 'bytes'
        try:
            # Update file name if specified
            content = headers['Content-Disposition'].split('=', 1)
            if content[0].endswith('filename'):
                self._name = content[1]
        except (KeyError, IndexError):
            pass

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
    __slots__ = ('_response', '_add_size', '_read', '_update_hash', '_file')

    def __init__(self, response, file):
        self._response = response
        self._file = file

        # Common functions
        self._add_size = file.add_size_callback
        self._read = self._response.raw.read
        if file.hash_obj is not None:
            self._update_hash = file.hash_obj.update
        else:
            self._update_hash = None

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

        # Compute hash
        if self._update_hash:
            self._update_hash(chunk)

        return chunk

    def tell(self):
        """
        Return current read position.

        Returns:
            int: Position.
        """
        return self._file.size_done
