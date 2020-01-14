# coding=utf-8
"""Tar archives"""

from nun._destination import Destination
from nun._exceptions import CancelException
from nun._files import FileBase
import tarfile


_TYPES = {
    tarfile.LNKTYPE: 'link',
    tarfile.SYMTYPE: 'link',
    tarfile.DIRTYPE: 'dir'
}


class File(FileBase):
    """Tar archives"""

    def _extract(self):
        """
        Extract the file.

        Returns:
            list of nun._destination.Destination: destinations
        """
        # TODO: handle
        #  - mode, uname (or uid if absent),
        #    gname ( or gid if absent)
        #  - dirs, links, ...
        #  - handle tarfile.TarError

        with tarfile.open(fileobj=self._get()) as archive:
            dests = []
            extractfile = archive.extractfile
            append_dest = dests.append
            set_path = self._set_path
            next_member = archive.next
            get_type = _TYPES.get

            while True:
                member = next_member()
                if member is None:
                    break

                path = set_path(member.name)
                member_type = get_type(member.type, 'file')

                try:
                    dest = Destination(
                        path, mtime=member.mtime, dst_type=member_type)

                    if member_type == 'file':
                        data = extractfile(member)
                    elif member_type == 'link':
                        data = member.linkname
                    else:
                        data = None

                    dest.write(data)
                    dest.close()
                    append_dest(dest)
                except CancelException:
                    # TODO: Log error messages at the higher level
                    continue

        return dests
