# coding=utf-8
"""Database"""

from contextlib import contextmanager
from json import dumps
from os.path import join
from sqlite3 import connect, Row
from time import time

from nun._config import DATA_DIR

# Database definition
_TABLES = {
    # Transactions
    'transactions': (
        ('id', 'INTEGER PRIMARY KEY'),
        ('timestamp', 'FLOAT'),
    ),
    # "Tasks" to perform and keep up to date
    'tasks': (
        ('id', 'INTEGER PRIMARY KEY'),
        # Latest transaction
        ('transaction_id', 'INTEGER'),
        # Resource
        ('resource', 'TEXT'),
        # Action performed on the resource
        ('action', 'INTEGER'),
        # Arguments of the action
        ('arguments', 'TEXT'),
    ),
    # A "task" use one or more remote "files" as source, depending on the
    # specified "resource".
    # "Files" may be simple files, archives containing other files or packages.
    # Simple files and archives will generate "destinations" on the local
    # filesystem.
    'files': (
        ('id', 'INTEGER PRIMARY KEY'),
        # Latest transaction
        ('transaction_id', 'INTEGER'),
        # Parents
        ('task_id', 'INTEGER'),
        # Name of the file
        ('name', 'TEXT'),
        # Value that represent the revision/version of the file
        ('revision', 'TEXT'),
        # Size of the remote file
        ('size', 'INTEGER'),
    ),
    # Destination are objects (Files, directories, ...) on the local filesystem
    # that are generated from resource "files".
    'destinations': (
        ('id', 'INTEGER PRIMARY KEY'),
        # Latest transaction
        ('transaction_id', 'INTEGER'),
        # Parents
        ('task_id', 'INTEGER'),
        ('file_id', 'INTEGER'),
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
    """The nun database"""
    __slots__ = ('_path', '_sql_cache')

    def __init__(self):
        self._path = join(DATA_DIR, 'nun.sqlite')

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

    def get_destination(self, path):
        """
        Get destination information from the database.

        Args:
            path (str): Absolute path on the local filesystem.

        Returns:
            sqlite3.Row: destination information.
        """
        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM destinations WHERE path=?', (path,))
            return cursor.fetchone()

    def get_destinations(self, file_id):
        """
        Get destination information from the database for a file.

        Args:
            file_id (int): ID of the parent task.

        Returns:
            list of sqlite3.Row: destinations information.
        """
        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM destinations WHERE file_id=?',
                           (file_id,))
            return cursor.fetchall()

    def get_file(self, task_id, name):
        """
        Get file information from the database.

        Args:
            task_id (int): ID of the parent task.
            name (str): Name of the file.

        Returns:
            sqlite3.Row: file information.
        """
        if task_id is None:
            return None

        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM files WHERE task_id=? AND name=?',
                           (task_id, name))
            return cursor.fetchone()

    def get_files(self, task_id):
        """
        Get files information from the database for a task.

        Args:
            task_id (int): ID of the parent task.

        Returns:
            list of sqlite3.Row: files information.
        """
        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM files WHERE task_id=?', (task_id,))
            return cursor.fetchall()

    def get_task(self, resource):
        """
        Get a single task information from the database.

        Args:
            resource (str): Resource.

        Returns:
            sqlite3.Row: task information.
        """
        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM tasks WHERE resource=?', (resource,))
            return cursor.fetchone()

    def get_tasks(self, resource):
        """
        Get multiples tasks information from the database.

        Args:
            resource (str): Resource glob pattern.

        Returns:
            list of sqlite3.Row: tasks information.
        """
        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM tasks WHERE resource GLOB ?',
                           (resource,))
            return cursor.fetchall()

    def set_transaction(self):
        """
        Create a new transaction in the database.

        Returns:
            int: Transaction ID.
        """
        with self._cursor() as cursor:
            cursor.execute(*self._sql_insert('transactions', timestamp=time()))
            return cursor.lastrowid

    def set_task(self, transaction_id, task_id=None, resource=None, action=None,
                 arguments=None, ref_values=None):
        """
        Add or update a task in the database.

        Args:
            transaction_id (int): Transaction ID.
            task_id (int): Task ID.
            resource (str): Resource.
            action (str): Action.
            arguments (dict): Action arguments.
            ref_values (sqlite3.Row): Previous row values.

        Returns:
            int: File ID.
        """
        if arguments:
            arguments = dumps(arguments)
        return self._sql_insert_or_update(
            'tasks', task_id, ref_values, resource=resource,
            transaction_id=transaction_id, action=action, arguments=arguments)

    def set_file(self, transaction_id, task_id=None, file_id=None, name=None,
                 revision=None, size=None, ref_values=None):
        """
        Add or update a file in the database.

        Args:
            transaction_id (int): Transaction ID.
            task_id (int): Task ID.
            file_id (int): File ID if already in the database.
            name (str): File name.
            revision (str): File revision.
            size (int): File size
            ref_values (sqlite3.Row): Previous row values.

        Returns:
            int: File ID.
        """
        return self._sql_insert_or_update(
            'files', file_id, ref_values, transaction_id=transaction_id,
            task_id=task_id, name=name, revision=revision, size=size)

    def set_destination(self, transaction_id, task_id=None, file_id=None,
                        path=None, digest=None, st_mode=None, st_uid=None,
                        st_gid=None, st_size=None, st_mtime=None, st_ctime=None,
                        ref_values=None):
        """
        Add or update a destination in the database.

        Args:
            transaction_id (int): Transaction ID.
            task_id (int): Task ID.
            file_id (int): File ID if already in the database.
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
            int: File ID.
        """
        return self._sql_insert_or_update(
            'destinations', file_id, ref_values, transaction_id=transaction_id,
            task_id=task_id, file_id=file_id, path=path, digest=digest,
            st_mode=st_mode, st_uid=st_uid, st_gid=st_gid, st_size=st_size,
            st_mtime=st_mtime, st_ctime=st_ctime)

    def del_task(self, task_id):
        """
        Delete a task from the database.

        Args:
            task_id (int): Task ID.
        """
        with self._cursor() as cursor:
            cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))

    def del_file(self, file_id):
        """
        Delete a file from the database, and all related destinations.

        Args:
            file_id (int): Destination ID.
        """
        with self._cursor() as cursor:
            cursor.execute('DELETE FROM files WHERE id = ?', (file_id,))
            cursor.execute('DELETE FROM destinations WHERE file_id = ?',
                           (file_id,))

    def del_destination(self, destination_id):
        """
        Delete a destination from the database.

        Args:
            destination_id (int): Destination ID.
        """
        with self._cursor() as cursor:
            cursor.execute('DELETE FROM destinations WHERE id = ?',
                           (destination_id,))

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
