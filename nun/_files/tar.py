# coding=utf-8
"""Tar archives"""

from nun._destination import Destination
from nun._exceptions import CancelException
from nun._files import FileBase
import tarfile


class File(FileBase):
    """Tar archives"""

    def _extract(self):
        """
        Extract the file.

        Returns:
            list of nun._destination.Destination: destinations
        """
        # TODO: handle
        #  - mode, type, linkname, uname (or uid if absent),
        #    gname ( or gid if absent)
        #  - dirs, links, ...
        #  - handle tarfile.TarError

        with tarfile.open(self._get()) as archive:
            dests = []
            extract = archive.extract
            append_dest = dests.append
            set_path = self._set_path
            next_member = archive.next

            while True:
                member = next_member()
                if member is None:
                    break

                path = set_path(member.name)
                try:
                    dest = Destination(path, mtime=member.mtime)
                    extract(member, dest)
                    dest.close()
                    append_dest(dest)
                except CancelException:
                    # TODO: Log error messages at the higher level
                    continue

        return dests
