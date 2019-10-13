"""Files & packages formats"""
# TODO:
#  - zip
#  - tar, tar.gz, ...
#  - deb
#  - rpm
#  - whl

from abc import ABC
from asyncio import create_task, CancelledError
from os import fsdecode, remove, rename
from os.path import join, isdir, realpath, dirname, expanduser

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

    async def download(self, output='.'):
        """
        Download file.

        Args:
            output (path-like object): Destination.

        Returns:
            list of str: Downloaded files paths.
        """
        resp = await self._get()
        output = self._set_output(output)
        tmp_output = output + '.tmp'
        write_task = None
        try:
            # Write file with temporary name
            async with aiopen(tmp_output, 'wb') as file:
                while True:
                    chunk = await resp.content.read(self._BUFFER_SIZE)
                    if write_task:
                        await write_task
                    if not chunk:
                        break
                    self._size_done += len(chunk)
                    write_task = create_task(file.write(chunk))

            # Move temporary file to final destination
            try:
                remove(output)
            except FileNotFoundError:
                pass
            rename(tmp_output, output)

        except CancelledError:
            # Remove partially downloaded file
            try:
                remove(tmp_output)
            except FileNotFoundError:
                pass
            return []
        return [output]

    async def extract(self, output='.'):
        """
        Extract file.

        Args:
            output (path-like object): Destination.

        Returns:
            list of str: Extracted files paths.
        """
        raise NotImplementedError(f'Extracting {self._name} is not supported.')

    async def install(self):
        """
        Install file.

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
