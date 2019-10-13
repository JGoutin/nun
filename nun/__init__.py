"""
nun
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
