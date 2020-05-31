"""Exceptions"""


class NunException(Exception):
    """Nun Base Exception"""


class CancelException(NunException):
    """Operation cancelled"""


class InvalidException(NunException):
    """Invalid operation"""


class NotFoundException(NunException):
    """Source not found"""
