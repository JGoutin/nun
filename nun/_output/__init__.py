"""Outputs"""

# Bytes units
_UNITS = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')


class OutputBase:
    """Base of output classes"""

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

    async def show_progress(self, files):
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