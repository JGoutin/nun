# coding=utf-8
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
__version__ = '1.0.0-alpha.1'

# TODO:
#  - Support formats: deb, rpm, whl, gz, xz, bz2
#  - Allow user to select file type to use
#  - Provides packages: WHL, DEB, RPM, chocolatey, Inno setup, exe zip
#  - Vendor dependencies if not packaged.
#  - Qt GUI
#  - Database: store resource, all generated files
#    On install/extract/download check files and remove files that does not
#    exists with new version.
#  - install args:
#    --cmd: install command to use, set default for some formats like deb
#    --exec: File itself is an executable file (May be zipped), to install in
#           "bin" with chmod +x
#  - download args:
#    --mode: Set file mode
#  - extract args:
#    --???: Create subdir with archive name
#  - install/download/extract common args:
#    --hash: Hash to check, "auto" to try to find from hash file, ...
#    --verify: Verify signature, like hash.
#  - Other commands:
#    update: update installed
#    list: list installed
#    info: info on installed
#    check: Files integrity check
#    remove: uninstall
#  - build before install feature (make, ...)
#  - install should also detect archives with unix structure and install it
#  - Get file URL from requests in json result
#  - Use Airfs as backend.
#  - platform: bitbucket
#  - platform: gitlab
#  - platform: git (Any git over internet)
#  - platform: http (any single file over internet)

from nun._manager import Manager as _Manager


def _perform(action, resources, **kwargs):
    """
    Perform action.

    Args:
        action (str): Action method.
        resources (iterable of str): Resources ID.
    """
    with _Manager(resources, action, **kwargs) as manager:
        manager.perform()


def download(resources, output='.', debug=False, force=False):
    """
    Download.

    Args:
        resources (iterable of str): Resources ID.
        output (path-like object): Destination.
        debug (bool): If True, show full error traceback and stop on first
                      error.
        force (bool): Replace any existing destination even if modified by user.
    """
    _perform('download', resources, output=output, debug=debug, force=force)


def extract(resources, output='.', debug=False, trusted=False,
            strip_components=0, force=False):
    """
    Extract.

    Args:
        resources (iterable of str): Resources ID.
        output (path-like object): Destination.
        debug (bool): If True, show full error traceback and stop on first
                      error.
        trusted (bool): If True, allow extraction of files outside of the
            output directory. Default to False, because this can be a
            security issue if extracted from an untrusted source.
        strip_components (int): strip NUMBER leading components from file
            path on extraction.
        force (bool): Replace any existing destination even if modified by user.
    """
    _perform('extract', resources, output=output, debug=debug, trusted=trusted,
             strip_components=strip_components, force=force)
