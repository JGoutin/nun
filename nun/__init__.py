"""
nun

Copyright (C) 2019 J.Goutin

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
# TODO:
# - Provides packages: WHL, DEB, RPM, chocolatey, Inno setup, exe zip
# - Vendor dependencies if not packaged.
# - Qt GUI
# - Database: store resource, all generated files
#   On install/extract/download check files and remove files that does not
#   exists with new version.

from nun._manager import Manager as _Manager


async def download(resources_ids, output='.', no_track=False):
    """
    Download.

    Args:
        resources_ids (iterable of str): Resources ID.
        output (path-like object): Destination.
        no_track (bool): If True, does not track file.
    """
    async with _Manager(
            resources_ids, no_track=no_track, output=output) as manager:
        await manager.download()
