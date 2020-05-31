"""Files & packages formats"""
from abc import ABC
from cgi import parse_header
from dateutil.parser import parse
from importlib import import_module
from os import fsdecode
from os.path import join, isdir, realpath, dirname, expanduser, isabs, splitext
from pathlib import PurePath

from requests import Session

from nun._dst import Dst, remove_existing
from nun._db import DB

#: File types aliases
ALIASES = {"tgz": "tar", "tbz": "tar", "tlz": "tar", "txz": "tar"}


def get_src(
    name,
    url,
    res_name,
    res_id,
    src_type=None,
    mtime=None,
    strip_components=0,
    revision=None,
):
    """
    Sources factory.

    Args:
        name (str): Source name.
        url (str): URL.
        res_name (str): Resource Name.
        res_id (int): Resource ID.
        src_type (str): File type to use if known in advance.
        mtime (int or float): Modification timestamp.
        strip_components (int): strip NUMBER leading components from file path when
            extracting an archive.
        revision (str): File revision.

    Returns:
        nun._src.SrcBase subclass instance: Source
    """
    # Detect file type based on its extension
    if src_type is None:
        filename, ext = splitext(name.lower())
        if ext in (".gz", ".bz2", ".lz", ".xz") and filename.endswith(".tar"):
            # Handle the ".tar.<compression>" special case
            src_type = "tar"
        else:
            src_type = ext.lstrip(".")

        src_type = ALIASES.get(src_type, src_type)

    try:
        cls = import_module(f"{__name__}.{src_type}").Src
    except ImportError:
        cls = SrcBase

    return cls(
        name,
        url,
        res_name,
        res_id,
        mtime=mtime,
        strip_components=strip_components,
        revision=revision,
    )


class SrcBase(ABC):
    """
    Source base.

    Args:
        src_name (str): Source name.
        url (str): URL.
        res_name (str): Resource.
        res_id (int): Resource ID.
        mtime (int or float or str): Modification time or timestamp.
        strip_components (int): strip NUMBER leading components from file path when
            extracting an archive.
        revision (str): File revision.
    """

    __slots__ = (
        "_name",
        "_url",
        "_res_name",
        "_size",
        "_res_id",
        "_size_done",
        "_done",
        "_exception",
        "_mtime",
        "_revision",
        "_output",
        "_trusted",
        "_db_info",
        "_src_id",
        "_dst_ids",
        "_session",
        "_strip_components",
    )

    def __init__(
        self,
        src_name,
        url,
        res_name,
        res_id,
        mtime=None,
        strip_components=0,
        revision=None,
    ):

        self._name = src_name
        self._url = url
        self._res_name = res_name
        self._done = False
        self._exception = None
        self._output = None
        self._strip_components = strip_components
        self._trusted = False
        self._res_id = res_id
        self._db_info = db_info = DB.get_src(res_id, src_name)
        self._revision = self._get_revision(revision)
        self._dst_ids = None
        self._session = Session()
        if db_info:
            self._src_id = db_info["id"]
        else:
            self._src_id = None

        if isinstance(mtime, str):
            mtime = parse(mtime).timestamp()
        self._mtime = mtime

        # For progress information
        self._size = 0
        self._size_done = 0

    @property
    def name(self):
        """
        Source name.

        Returns:
            str: name.
        """
        return self._name

    @property
    def res_name(self):
        """
        Resource name.

        Returns:
            str: resource name.
        """
        return self._res_name

    @property
    def size(self):
        """
        Source size.

        Returns:
            int: number of bytes.
        """
        return self._size

    @property
    def size_done(self):
        """
        Processed source size.

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
    def dst_ids(self):
        """
        Destinations IDs.

        Returns:
            None or set of int: Destinations IDs. If None, the file and its destinations
                are unchanged.
        """
        return self._dst_ids

    def _cancel(self, update, force):
        """
        Return True if cancel the operation.

        Args:
            update (bool): True if it is an update operation.
            force (bool): True if operation is forced to run.

        Returns:
            bool: True if cancelled.
        """
        if (
            update
            and not force
            and self._db_info is not None
            and self._revision == self._db_info.revision
        ):
            self._dst_ids = True
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

        resp = self._session.head(self._url)
        resp.raise_for_status()

        headers = resp.headers
        etag = headers.get("ETag")
        if etag and not etag.startswith("W/"):
            return etag
        else:
            return headers.get("Last-Modified")

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
    def src_id(self):
        """
        Source ID in database.

        Returns:
            int: Source ID.
        """
        return self._src_id

    def _db_update(self, tsk_id, dsts=None):
        """
        Update the source in the database.

        Args:
            tsk_id (int): Task ID.
            dsts (iterable of nun._dst.Dst): destinations.
        """
        # Update the source in the database
        self._src_id = src_id = DB.set_src(
            ref_values=self._db_info,
            tsk_id=tsk_id,
            res_id=self._res_id,
            name=self._name,
            revision=self._revision,
            size=self._size,
        )

        if dsts:
            # Update destinations in the database
            self._dst_ids = set()
            add = self._dst_ids.add
            kwargs = dict(tsk_id=tsk_id, res_id=self._res_id, src_id=src_id)

            for dst in dsts:
                add(dst.db_update(**kwargs))

    def remove_orphans(self):
        """
        Remove orphan destinations.
        """
        dst_ids = self._dst_ids
        del_dst = DB.del_dst
        for dst_row in DB.get_dst_by_src(self._src_id):
            if dst_row["id"] not in dst_ids:
                remove_existing(dst_row["path"])
                del_dst(dst_row["id"])

    def download(self, output=".", force=False, update=False, tsk_id=None):
        """
        Download the file.

        Args:
            output (path-like object): Destination.
            force (bool): Force update and replace any existing destination even if
                modified by user.
            update (bool): If True, is an update of an already in the database entry.
            tsk_id (int): Task ID.
        """
        if self._cancel(update, force):
            return

        self._set_output(output)
        path = self._set_path(self._name, strip_components=0)

        # Force strip_components=0 on a single file
        with Dst(path, force=force, res_id=self._res_id) as dst:
            dst.write(self._get())
            dst.move(self._mtime)
            dst.clear()

        self._db_update(tsk_id, (dst,))

    def extract(
        self,
        output=".",
        trusted=False,
        strip_components=0,
        force=False,
        update=False,
        tsk_id=None,
    ):
        """
        Extract the file.

        Args:
            output (path-like object): Destination.
            trusted (bool): If True, allow extraction of files outside of the output
                directory. Default to False, because this can be a security issue if
                extracted from an untrusted source.
            strip_components (int): strip NUMBER leading components from file path on
                extraction.
            force (bool): Force update and replace any existing destination even if
                modified by user.
            update (bool): If True, is an update of an already in the database entry.
            tsk_id (int): Task ID.
        """
        if self._cancel(update, force):
            return

        self._trusted = trusted
        self._set_output(output)
        if strip_components != 0:
            self._strip_components = strip_components

        # Perform operation sequentially to allow to revert back on error
        dsts = self._extract()

        for dst in dsts:
            dst.move()

        for dst in dsts:
            dst.clear()

        self._db_update(tsk_id, dsts)

    def _extract(self):
        """
        Extract the file.

        Returns:
            list of nun._dst.Dst: destinations
        """
        raise NotImplementedError(f"extracting {self._name} is not supported.")

    def install(self, force=False, update=False, tsk_id=None):
        """
        Install the file.

        Args:
            force (bool): Force update and replace any existing destination even if
                modified by user.
            update (bool): If True, is an update of an already in the database entry.
            tsk_id (int): Task ID.
        """
        if self._cancel(update, force):
            return

        self._install()
        self._db_update(tsk_id)

    def _install(self):
        """
        Install the file.
        """
        raise NotImplementedError(f"Installing {self._name} is not supported.")

    def _get(self):
        """
        Performs a get request on file URL.

        Returns:
            file-like object: Response content.
        """
        # Perform requests and handle exceptions
        resp = self._session.get(self._url, stream=True)
        resp.raise_for_status()

        # Get information from headers
        headers = resp.headers
        self._size = int(headers.get("Content-Length", 0))
        if self._mtime is None:
            try:
                self._mtime = parse(headers["Last-Modified"]).timestamp()
            except KeyError:
                pass

        # Update file name if specified
        try:
            self._name = parse_header(headers["Content-Disposition"])[1]["filename"]
        except KeyError:
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

    def _set_path(self, path, target_is_dir=False, strip_components=None):
        """
        Set final destination path.

        Args:
            path (str): Object path.
            target_is_dir (bool): Target is a directory.
            strip_components (int): strip NUMBER leading components from file path.

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
        if not self._trusted and (absolute or path.startswith("..")):
            raise PermissionError(
                f'The "{self._name}" target a destination outside of the output '
                f'directory. If you trust this source, use the "trusted" option to '
                f"allow this behavior."
            )

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
                f'Output directory "{dirname(self._output)}" does not exists.'
            )

        # This directory is a new sub-directory
        return self._output


class Body:
    """
    Body file like object

    Args:
        response (requests.Response): Response.
        src (nun._src.SrcBase subclass): Source.
    """

    __slots__ = ("_response", "_add_size", "_read", "_src")

    def __init__(self, response, src):
        self._response = response
        self._src = src

        # Common functions
        self._add_size = src.add_size_callback
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
        return self._src.size_done
