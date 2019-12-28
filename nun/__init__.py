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
__version__ = '1.0.0'

# TODO:
# - Provides packages: WHL, DEB, RPM, chocolatey, Inno setup, exe zip
# - Vendor dependencies if not packaged.
# - Qt GUI
# - Database: store resource, all generated files
#   On install/extract/download check files and remove files that does not
#   exists with new version.

from nun._manager import Manager as _Manager


def _perform(action, resources_ids, **kwargs):
    """
    Perform action.

    Args:
        action (str): Action method.
        resources_ids (iterable of str): Resources ID.
    """
    with _Manager(resources_ids, **kwargs) as manager:
        manager.perform(action)


def download(resources_ids, output='.', no_track=False, debug=False,
             force=False):
    """
    Download.

    Args:
        resources_ids (iterable of str): Resources ID.
        output (path-like object): Destination.
        no_track (bool): If True, does not track file.
        debug (bool): If True, show full error traceback and stop on first
                      error.
        force (bool): Replace any existing destination even if modified by user.
    """
    _perform('download', resources_ids, output=output, no_track=no_track,
             debug=debug, force=force)


def extract(resources_ids, output='.', no_track=False, debug=False,
            trusted=False, strip_components=0, force=False):
    """
    Extract.

    Args:
        resources_ids (iterable of str): Resources ID.
        output (path-like object): Destination.
        no_track (bool): If True, does not track file.
        debug (bool): If True, show full error traceback and stop on first
                      error.
        trusted (bool): If True, allow extraction of files outside of the
            output directory. Default to False, because this can be a
            security issue if extracted from an untrusted source.
        strip_components (int): strip NUMBER leading components from file
            path on extraction.
        force (bool): Replace any existing destination even if modified by user.
    """
    _perform('extract', resources_ids, output=output, no_track=no_track,
             debug=debug, trusted=trusted,
             strip_components=strip_components, force=force)
