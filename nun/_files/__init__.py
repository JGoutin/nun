"""Files & packages formats"""
# TODO:
#  Support formats:
#  - zip
#  - tar, tar.gz, ...
#  - deb
#  - rpm
#  - whl
#  File from a link inside a JSON request
#  File replacement method (To apply to "extract" and "download")
#  - Compute hash
#  - Compare hash, if identical previously stored, skip
#  - Compare existing hash with sorted one: if file modified (by user), skip
#    (except if "--replace" option)
#  - write new file as "<name>.part.nun"
#  - Once all files written, move "<name>" to "<name>.bak.nun"
#  - Once all moved, move "<name>.part.nun" to "<name>"
#  - If everything is OK, remove "<name>.bak.nun", store new hash and remove
#    files that not exists with new version (If not modified)
#  - If anything fail, revert back "<name>.bak.nun" to "<name>" and
#    delete "<name>.part.nun".

from abc import ABC
from asyncio import create_task, CancelledError
from os import fsdecode, remove, rename, mkdir
from os.path import join, isdir, realpath, dirname, expanduser, isabs

from aiofiles import open as aiopen


class FileBase(ABC):
    """
    File base.

    Args:
        name (str): File name.
        url (str): URL.
        resource (nun._platforms.ResourceBase subclass instance): Resource.
    """
    __slots__ = ('_name', '_url', '_resource', '_request', '_size',
                 '_size_done', '_done', '_mime_type', '_task')

    _BUFFER_SIZE = 65536

    def __init__(self, name, url, resource):
        self._name = name
        self._url = url
        self._resource = resource
        self._request = self._resource.platform.request
        self._done = False
        self._mime_type = None
        self._task = None

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
    def task(self):
        """
        Operation completed

        Returns:
            bool: True if done.
        """
        return self._task

    def set_task(self, task):
        """
        Set the task used to perform file operation.

        Args:
            task (asyncio.Task): Task.
        """
        self._task = task

    async def _download(self, path=None):
        """
        Download the file to the specified path

        Args:
            path (path-like object): Destination.
        """
        resp = await self._get()

        # Write the file with temporary name
        try:
            async with aiopen(path, 'wb') as file:
                write_task = None
                while True:
                    chunk = await resp.content.read(self._BUFFER_SIZE)
                    if write_task:
                        await write_task
                    if not chunk:
                        break
                    self._size_done += len(chunk)
                    write_task = create_task(file.write(chunk))

        except CancelledError:
            # Remove partially downloaded file
            try:
                remove(path)
            except FileNotFoundError:
                pass

    async def download(self, output='.'):
        """
        Download the file.

        Args:
            output (path-like object): Destination.

        Returns:
            list of str: Downloaded files paths.
        """
        try:
            output = self._set_output(output)
            tmp_output = output + '.tmp'

            # Download the file to a temporary path
            await self._download(tmp_output)

            # Remove any previously existing file
            try:
                remove(output)
            except FileNotFoundError:
                pass

            # Move the temporary file to the final destination
            rename(tmp_output, output)

        except CancelledError:
            return []
        return [output]

    def _abs_paths(self, paths, output, trusted):
        """
        Check no paths are outside the working directory and return a list
        of absolutes paths.

        Args:
            paths (iterable of str): Paths to check
            output (str): Destination.
            trusted (bool): If True, allow files outside of the
                output directory.

        Raises:
            PermissionError: If "trusted" is False and at least one path is
                outside the working directory.

        Returns:
            list of str: absolute result paths.
        """
        result = []
        for path in paths:
            if not trusted and (isabs(path) or path.startswith('..')):
                raise PermissionError(
                    f'The "{self._name}" archive contain files that will '
                    'be extracted outside of the output directory. If you '
                    'trust this archive source, use the "trusted" option '
                    'to allow this behavior.')
            elif not isabs(path):
                path = join(output, path)
            result.append(path)
        return result

    async def extract(self, output='.', trusted=False, strip_components=0):
        """
        Extract the file.

        Args:
            output (path-like object): Destination.
            trusted (bool): If True, allow extraction of files outside of the
                output directory. Default to False, because this can be a
                security issue if extracted from an untrusted source.
            strip_components (int): strip NUMBER leading components from file
                path on extraction.

        Returns:
            list of str: Extracted files paths.
        """
        from shutil import rmtree
        # TODO:
        #       - strip_components
        #       - Async stream and uncompress instead of using intermediate
        #         temporary file
        tmp_output = output + '.tmp'
        mkdir(tmp_output)
        try:

            # Download to a temporary file because tarfile/zipfile does not
            # support asyncio
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as tmp:
                tmp_path = join(tmp, self._name)
                await self._download(tmp_path)

                # Try with TAR
                import tarfile
                if tarfile.is_tarfile(tmp_path):
                    file = tarfile.open(tmp_path)
                    names = self._abs_paths(
                        file.getnames(), tmp_output, trusted)
                    file.extractall(tmp_output)

                # Try with ZIP
                import zipfile
                if zipfile.is_zipfile(tmp_path):
                    file = zipfile.ZipFile(tmp_path)
                    names = self._abs_paths(
                        file.namelist(), tmp_output, trusted)
                    file.extractall(tmp_output)

            if names:
                rename(tmp_output, output)
                return names

            else:
                remove(tmp_output)
                raise NotImplementedError(
                    f'Extracting {self._name} is not supported.')

        except CancelledError:
            rmtree(tmp_output, ignore_errors=True)
            return []

    async def install(self):
        """
        Install the file.

        Returns:
            list of str: Installed files paths.
        """
        raise NotImplementedError(f'Installing {self._name} is not supported.')

    async def _get(self):
        """
        Performs a get request on file URL.

        Returns:
            aiohttp.client_reqrep.ClientResponse: Response.
        """
        # TODO: Parallel download
        # Perform requests and handle exceptions
        resp = await self._request(self._url)
        await self._resource.exception_handler(resp.status, self._name)

        # Get information from headers
        headers = resp.headers
        self._size = int(headers.get('Content-Length', 0))
        self._mime_type = headers.get('Content-Type')
        try:
            # Update file name if specified
            content = headers['Content-Disposition'].split('=', 1)
            if content[0].endswith('filename'):
                self._name = content[1]
        except (KeyError, IndexError):
            pass

        return resp

    def _set_output(self, output, target_is_dir=False):
        """
        Set final destination path.

        Args:
            output (path-like object): Destination.
            target_is_dir (bool): Target is a directory.

        Returns:
            str: Destination absolute path.
        """
        output = realpath(expanduser(fsdecode(output)))

        if isdir(output):
            # Destination is this directory
            if target_is_dir:
                return output

            # Destination is a file in this directory
            return join(output, self._name)

        # Parent directory does not exists
        if not isdir(dirname(output)):
            raise FileNotFoundError(
                f'Output directory "{dirname(output)}" does not exists.')

        # This directory is a new sub-directory
        return output
