# coding=utf-8
"""Database"""

from sqlite3 import connect
from os.path import join

from nun._config import DATA_DIR


class _Database:
    """The nun database"""
    __slots__ = ('_con',)

    def __init__(self):
        self._con = connect(join(DATA_DIR, 'nun.sqlite'))


# Use a single database instance
DB = _Database()
