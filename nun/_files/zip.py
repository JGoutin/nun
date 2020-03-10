# coding=utf-8
"""Zip archives"""

from os.path import join
from shutil import copyfileobj
from tempfile import TemporaryDirectory
from datetime import datetime
import zipfile

from nun._destination import Destination
from nun._exceptions import CancelException
from nun._files import FileBase


class File(FileBase):
    """Zip archives"""

    def _extract(self):
        """
        Extract the file.

        Returns:
            list of nun._destination.Destination: destinations
        """
        # TODO: handle
        #  - handle zipfile.BadZipFile
        #  - external_attr
        #  - passwords
        with TemporaryDirectory(prefix='nun_') as tmp:
            # Use a temporary file, Zip cannot be directly streamed like Tar
            tmp_zip = join(tmp, "z.zip")
            with open(tmp_zip, 'wb') as zip_file:
                copyfileobj(self._get(), zip_file)

            with zipfile.ZipFile(tmp_zip) as archive:
                dests = []
                member_open = archive.open
                append_dest = dests.append
                set_path = self._set_path

                for member in archive.infolist():
                    path = set_path(member.filename)
                    member_type = 'dir' if member.is_dir() else 'file'

                    mtime = datetime(*member.date_time).timestamp()
                    try:
                        dest = Destination(path, dst_type=member_type,
                                           mtime=mtime, task_id=self._task_id)

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
