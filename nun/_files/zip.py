# coding=utf-8
"""Tar archives"""

from nun._destination import Destination
from nun._exceptions import CancelException
from nun._files import FileBase
import zipfile


class File(FileBase):
    """Tar archives"""

    def _extract(self):
        """
        Extract the file.

        Returns:
            list of nun._destination.Destination: destinations
        """
        # TODO: handle
        #  - handle tarfile.TarError
        #  - mtime from "date_time"
        #  - dirs
        #  - external_attr
        #  - passwords

        with zipfile.ZipFile(self._get()) as archive:
            dests = []
            extract = archive.extract
            append_dest = dests.append
            set_path = self._set_path

            for member in archive.infolist():
                path = set_path(member.name)
                try:
                    dest = Destination(path)
                    extract(member, dest)
                    dest.close()
                    append_dest(dest)
                except CancelException:
                    # TODO: Log error messages at the higher level
                    continue
        return dests
