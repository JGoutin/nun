# coding=utf-8
"""Database"""

from contextlib import contextmanager
from json import dumps
from os.path import join
from sqlite3 import connect, Row
from time import time

from nun._cfg import DATA_DIR, APP_NAME

# Database definition
_TABLES = {
    # Tasks
    'tsk': (
        ('id', 'INTEGER PRIMARY KEY'),
        ('timestamp', 'FLOAT'),
    ),
    # Resources
    'res': (
        ('id', 'INTEGER PRIMARY KEY'),
        # Latest task
        ('tsk_id', 'INTEGER'),
        # Resource name
        ('name', 'TEXT'),
        # Action performed on the resource
        ('action', 'INTEGER'),
        # Arguments of the action
        ('arguments', 'TEXT'),
    ),
    # Sources
    'src': (
        ('id', 'INTEGER PRIMARY KEY'),
        # Latest task
        ('tsk_id', 'INTEGER'),
        # Parents
        ('res_id', 'INTEGER'),
        # Name of the source
        ('name', 'TEXT'),
        # Value that represent the revision/version of the source
        ('revision', 'TEXT'),
        # Size of the remote source
        ('size', 'INTEGER'),
    ),
    # Destinations
    'dst': (
        ('id', 'INTEGER PRIMARY KEY'),
        # Latest task
        ('tsk_id', 'INTEGER'),
        # Parents
        ('res_id', 'INTEGER'),
        ('src_id', 'INTEGER'),
        # Absolute path on the local filesystem
        ('path', 'TEXT'),
        # Black2s hash digest
        ('digest', 'TEXT'),
        # Filesystem stat attributes
        ('st_mode', 'INTEGER'),
        ('st_uid', 'INTEGER'),
        ('st_gid', 'INTEGER'),
        ('st_size', 'INTEGER'),
        ('st_mtime', 'INTEGER'),
        ('st_ctime', 'INTEGER'),
    )
}


def _list_columns():
    """
    List columns by tables.

    Returns:
        dict: Columns per table
    """
    return {table: tuple(col[0] for col in cols if col[0] != 'id')
            for table, cols in _TABLES.items()}


_COLUMNS = _list_columns()


class _Database:
    """Application database"""
    __slots__ = ('_path', '_sql_cache')

    def __init__(self):
        self._path = join(DATA_DIR, f'{APP_NAME}.sqlite')

        # Cached SQL queries
        self._sql_cache = {}

        # Ensure tables exists
        with self._cursor() as cursor:
            for table, columns in _TABLES.items():
                cursor.execute(
                    f'CREATE TABLE IF NOT EXISTS {table}'
                    f'({", ".join(" ".join(column) for column in columns)})')

    @contextmanager
    def _cursor(self):
        """
        Database cursor.

        Returns:
            sqlite3.Cursor: Database cursor.
        """
        connexion = connect(self._path)
        try:
            connexion.row_factory = Row
            with connexion:
                yield connexion.cursor()

        finally:
            connexion.close()

    def get_dst(self, dst_path):
        """
        Get destination information.

        Args:
            dst_path (str): Destination path.

        Returns:
            sqlite3.Row: destination information.
        """
        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM dst WHERE path=?', (dst_path,))
            return cursor.fetchone()

    def get_dst_by_src(self, src_id):
        """
        Get all destination information for a same source.

        Args:
            src_id (int): Source ID.

        Returns:
            list of sqlite3.Row: destinations information.
        """
        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM dst WHERE src_id=?', (src_id,))
            return cursor.fetchall()

    def get_src(self, res_id, src_name):
        """
        Get source information.

        Args:
            res_id (int): Source ID.
            src_name (str): Source name.

        Returns:
            sqlite3.Row: Source information.
        """
        if res_id is None:
            return None

        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM src WHERE res_id=? AND name=?',
                           (res_id, src_name))
            return cursor.fetchone()

    def get_src_by_res(self, res_id):
        """
        Get all sources information for a same resource.

        Args:
            res_id (int): Resource ID.

        Returns:
            list of sqlite3.Row: sources information.
        """
        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM src WHERE res_id=?', (res_id,))
            return cursor.fetchall()

    def get_res_by_glob(self, res_name):
        """
        Get multiples resources information.

        Args:
            res_name (str): Resource name glob pattern.

        Returns:
            list of sqlite3.Row: resources information.
        """
        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM res WHERE name GLOB ?', (res_name,))
            return cursor.fetchall()

    def set_tsk(self):
        """
        Insert a task.

        Returns:
            int: Task ID.
        """
        with self._cursor() as cursor:
            cursor.execute(*self._sql_insert('tsk', timestamp=time()))
            return cursor.lastrowid

    def set_res(self, tsk_id, res_id=None, name=None, action=None,
                arguments=None, ref_values=None):
        """
        Insert or update a resource.

        Args:
            tsk_id (int): Task ID.
            res_id (int): Resource ID. Perform update if specified, else insert.
            name (str): Resource name.
            action (str): Action.
            arguments (dict): Action arguments.
            ref_values (sqlite3.Row): Previous row values.

        Returns:
            int: Resource ID.
        """
        if arguments:
            arguments = dumps(arguments)
        return self._sql_insert_or_update(
            'res', res_id, ref_values, name=name, tsk_id=tsk_id, action=action,
            arguments=arguments)

    def set_src(self, tsk_id, res_id=None, src_id=None, name=None,
                revision=None, size=None, ref_values=None):
        """
        Insert or update a source.

        Args:
            tsk_id (int): Task ID.
            res_id (int): Resource ID.
            src_id (int): Source ID. Perform update if specified, else insert.
            name (str): Source name.
            revision (str): File revision.
            size (int): File size
            ref_values (sqlite3.Row): Previous row values.

        Returns:
            int: Source ID.
        """
        return self._sql_insert_or_update(
            'src', src_id, ref_values, tsk_id=tsk_id,
            res_id=res_id, name=name, revision=revision, size=size)

    def set_dst(self, tsk_id, res_id=None, src_id=None,
                path=None, digest=None, st_mode=None, st_uid=None,
                st_gid=None, st_size=None, st_mtime=None, st_ctime=None,
                ref_values=None):
        """
        Insert or update a destination.

        Args:
            tsk_id (int): Task ID.
            res_id (int): Resource ID.
            src_id (int): Source ID.
            path (str): Path.
            digest (str): Digest.
            st_mode (int): mode
            st_uid (int): UID
            st_gid (int): GID
            st_size (int): Size
            st_mtime (int): Modification time.
            st_ctime (int): Creation time.
            ref_values (sqlite3.Row): Previous row values.

        Returns:
            int: Destination ID.
        """
        return self._sql_insert_or_update(
            'dst', src_id, ref_values, tsk_id=tsk_id,
            res_id=res_id, src_id=src_id, path=path, digest=digest,
            st_mode=st_mode, st_uid=st_uid, st_gid=st_gid, st_size=st_size,
            st_mtime=st_mtime, st_ctime=st_ctime)

    def del_res(self, res_id):
        """
        Delete a resource from the database.

        Args:
            res_id (int): Resource ID.
        """
        with self._cursor() as cursor:
            cursor.execute('DELETE FROM res WHERE id = ?', (res_id,))

    def del_src(self, src_id):
        """
        Delete a source and all related destinations.

        Args:
            src_id (int): Source ID.
        """
        with self._cursor() as cursor:
            cursor.execute('DELETE FROM src WHERE id = ?', (src_id,))
            cursor.execute('DELETE FROM dst WHERE src_id = ?', (src_id,))

    def del_dst(self, dst_id):
        """
        Delete a destination.

        Args:
            dst_id (int): Destination ID.
        """
        with self._cursor() as cursor:
            cursor.execute('DELETE FROM dst WHERE id = ?', (dst_id,))

    def _sql_insert_or_update(self, table, row_id=None, ref_values=None,
                              **values):
        """
        UPDATE or INSERT row in a table.

        Args:
            table (str): Table.
            row_id (int): Row ID.
            ref_values (sqlite3.Row): Previous row values.
            **values: Row values.

        Returns:
            int: Row ID.
        """
        with self._cursor() as cursor:
            # Row ID or previous values: UPDATE
            if row_id is not None or ref_values is not None:
                sql, parameters = self._sql_update(
                    table, row_id, ref_values, **values)
                cursor.execute(sql, parameters)
                return parameters['row_id']

            # INSERT
            cursor.execute(*self._sql_insert(table, **values))
            return cursor.lastrowid

    def _sql_update(self, table, row_id=None, ref_values=None, **values):
        """
        Create an UPDATE query to update a row by its ID.

        Args:
            table (str): Table.
            row_id (int): Row ID.
            ref_values (sqlite3.Row): Previous row values.
            **values: Row values.

        Returns:
            tuple: sql str, parameters dict.
        """
        # Define ID
        if row_id is None:
            row_id = ref_values['id']

        # Define values to update
        elif ref_values is None:
            ref_values = dict()

        get_value = ref_values.get
        parameters = {key: value for key, value in values.items()
                      if value is not None and value != get_value(key)}

        # Write query
        cols = tuple(sorted(parameters))
        try:
            sql = self._sql_cache[(table, cols)]
        except KeyError:
            values = ', '.join(f'{col} = :{col}' for col in cols)
            sql = self._sql_cache[(table, cols)] = (
                f'UPDATE {table} SET {values} WHERE id = :row_id')

        parameters['row_id'] = row_id
        return sql, parameters

    def _sql_insert(self, table, **values):
        """
        Create an INSERT query.

        Args:
            table (str): Table.
            **values: Row values.

        Returns:
            tuple: sql str, parameters tuple.
        """
        cols = _COLUMNS[table]
        try:
            sql = self._sql_cache[table]
        except KeyError:
            self._sql_cache[table] = sql = (
                f'INSERT INTO {table}({",".join(cols)}) '
                f'VALUES ({",".join("?" * len(cols))})')
        return sql, tuple(values[col] for col in cols)


# Use a single database instance
DB = _Database()
