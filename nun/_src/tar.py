# coding=utf-8
"""Tar archives"""

import tarfile

from nun._dst import Dst
from nun.exceptions import CancelException
from nun._src import SrcBase


_TYPES = {
    tarfile.LNKTYPE: 'link',
    tarfile.SYMTYPE: 'link',
    tarfile.DIRTYPE: 'dir'
}


class Src(SrcBase):
    """Tar archives"""

    def _extract(self):
        """
        Extract the file.

        Returns:
            list of nun._dst.Dst: destinations
        """
        # TODO: handle
        #  - mode, uname (or uid if absent), gname ( or gid if absent)
        #  - handle tarfile.TarError

        with tarfile.open(fileobj=self._get()) as archive:
            dsts = []
            extractfile = archive.extractfile
            append_dst = dsts.append
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
                    dst = Dst(path, mtime=member.mtime, dst_type=member_type,
                              res_id=self._res_id)

                    if member_type == 'file':
                        data = extractfile(member)
                    elif member_type == 'link':
                        data = member.linkname
                    else:
                        data = None

                    dst.write(data)
                    dst.close()
                    append_dst(dst)
                except CancelException:
                    # TODO: Log error messages at the higher level
                    continue

        return dsts
