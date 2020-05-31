"""nun"""

# Copyright (C) 2019 J.Goutin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__version__ = "1.0.0-alpha.1"

# TODO:
#  - dest should keep user specified "mode", "UID", "GID", except with --force
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
#  - git: Parse ".gitmodules" and retrieve submodules

from nun._ui import set_ui
from nun._tsk import Tsk as _Tsk


def download(resources, output=".", debug=False, force=False):
    """
    Download resources.

    Args:
        resources (iterable of str): Resources URLs.
        output (path-like object): Output path.
        debug (bool): If True, show full error traceback and stop on first error.
        force (bool): Replace any existing destination even if modified by user.
    """
    with _Tsk(resources, "download", output=output, debug=debug, force=force) as tsk:
        tsk.apply()


def extract(
    resources, output=".", debug=False, trusted=False, strip_components=0, force=False
):
    """
    Extract resources.

    Args:
        resources (iterable of str): Resources URLs.
        output (path-like object): Output path.
        debug (bool): If True, show full error traceback and stop on first error.
        trusted (bool): If True, allow extraction of files outside of the output
            directory. Default to False, because this can be a security issue if
            extracted from an untrusted source.
        strip_components (int): strip NUMBER leading components from file path on
            extraction.
        force (bool): Replace any existing destination even if modified by user.
    """
    with _Tsk(
        resources,
        "extract",
        output=output,
        debug=debug,
        force=force,
        trusted=trusted,
        strip_components=strip_components,
    ) as tsk:
        tsk.apply()


def install(resources, debug=False, force=False):
    """
    Install resources.

    Args:
        resources (iterable of str): Resources URLs.
        debug (bool): If True, show full error traceback and stop on first error.
        force (bool): Replace any existing destination even if modified by user.
    """
    with _Tsk(resources, "install", debug=debug, force=force) as tsk:
        tsk.apply()


def remove(resources="*", debug=False):
    """
    Remove resources.

    Args:
        resources (iterable of str): Resources URLs.
        debug (bool): If True, show full error traceback and stop on first error.
    """
    with _Tsk(resources, "remove", debug=debug) as tsk:
        tsk.apply()


def update(resources="*", debug=False, force=False):
    """
    Update resources.

    Args:
        resources (iterable of str): Resources URLs.
        debug (bool): If True, show full error traceback and stop on first error.
        force (bool): Replace any existing destination even if modified by user.
    """
    with _Tsk(resources, "update", debug=debug, force=force) as tsk:
        tsk.apply()
