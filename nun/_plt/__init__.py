"""Platforms"""

from abc import ABC, abstractmethod
from importlib import import_module
from threading import Lock

_PLATFORMS = dict()
_LOCK = Lock()


def get_plt(res_name):
    """
    Get platform associated to a resource name.

    Args:
        res_name (str): Resource name.

    Returns:
        nun._plt.PltBase subclass: Platform.
    """
    sch = res_name.split('://', 1)[0]

    with _LOCK:
        # Get cached platform
        try:
            return _PLATFORMS[sch]

        # Or, instantiate the platform and cache it
        except KeyError:
            plt = _PLATFORMS[sch] = import_module(f'{__name__}.{sch}').Plt()
            return plt


class PltBase(ABC):
    """
    Platform base class.
    """

    @abstractmethod
    def get_src_list(self, res_name, res_id):
        """
        Get sources from a specific resource.

        Args:
            res_name (str): Resource name.
            res_id (int): Resource ID.

        Returns:
            iterable of nun._src.SrcBase subclass: Sources.
        """
