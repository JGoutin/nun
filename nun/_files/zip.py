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
        #  - Requires random read access
        #  - handle zipfile.BadZipFile
        #  - mtime from "date_time"
        #  - dirs
        #  - external_attr
        #  - passwords

        with zipfile.ZipFile(self._get()) as archive:
            dests = []
            member_open = archive.open
            append_dest = dests.append
            set_path = self._set_path

            for member in archive.infolist():
                path = set_path(member.name)
                member_type = 'dir' if member.is_dir() else 'file'
                try:
                    dest = Destination(path, dst_type=member_type)

                    if member_type == 'file':
                        data = member_open(member)
                    else:
                        data = None

                    dest.write(data)
                    dest.close()
                    append_dest(dest)
                except CancelException:
                    # TODO: Log error messages at the higher level
                    continue
        return dests
