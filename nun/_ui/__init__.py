# coding=utf-8
"""Outputs"""
from importlib import import_module

# Bytes units
_UNITS = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')

_UI = dict()


def set_ui(ui_type):
    """
    Set default user interface.

    Args:
        ui_type (str) User interface type.
    """
    UiBase.DEFAULT = ui_type


def get_ui(ui_type=None):
    """
    Get user interface

    Args:
        ui_type (str) User interface type.

    Returns:
        nun._ui.UiBase subclass: output.
    """
    ui_type = ui_type or UiBase.DEFAULT
    try:
        return _UI[ui_type]
    except KeyError:
        if ui_type:
            ui = import_module(f'{__name__}.{UiBase.DEFAULT}').Ui()
        else:
            ui = UiBase()
        _UI[ui_type] = ui
        return ui


class UiBase:
    """Base of UI classes"""

    #: Default UI type to use
    DEFAULT = None

    __slots__ = ()

    def info(self, text):
        """
        Show info

        Args:
            text (str): text.
        """

    def warn(self, text):
        """
        Show warning

        Args:
            text (str): text.
        """
        import warnings
        warnings.warn(text)

    def error(self, text):
        """
        Show error.

        Args:
            text (str): text.
        """

    def show_progress(self, files):
        """
        Show progression

        Args:
            files (iterable of nun._files.FileBase): Files in progress.
        """

    @staticmethod
    def _get_unit(nb_bytes):
        """
        Get unit of number of bytes.

        Args:
            nb_bytes (int or float): Number of bytes.

        Returns:
            tuple: float value, unit
        """
        unit = 0
        while nb_bytes > 1000:
            unit += 1
            nb_bytes /= 1000
        return float(nb_bytes), _UNITS[unit]
