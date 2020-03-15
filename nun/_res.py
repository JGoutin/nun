"""Tasks"""
from nun._db import DB
from nun._dst import remove_existing
from nun._plt import get_plt
from nun.exceptions import InvalidException


class Res:
    """Resource"""
    __slots__ = ('_name', '_res_id', '_tsk_id', '_action', '_arguments')

    def __init__(self, tsk_id, res_id=None, name=None, action=None,
                 arguments=None):
        self._tsk_id = tsk_id
        self._name = name
        self._action = action
        self._arguments = arguments

        # New resource: Checks if exists in database
        if not res_id:
            res_id = DB.get_src(res_id, name)['id']
        self._res_id = res_id

    def apply(self, task_action, submit, force=False):
        """
        Apply the task action on the resource.

        Args:
            task_action (str): Task action to apply.
            submit (function): Task executor submit function.
            force (bool): If True, force operation.
        """
        if task_action == 'update':
            self._update(submit, force)
        elif task_action == 'remove':
            self._remove(submit)
        else:
            self._create(submit, force)

    def _create(self, submit, force=False):
        """
        Create a new resource.

        Args:
            submit (function): Task executor submit function.
            force (bool): If True, force operation.
        """
        if not force and self._res_id:
            raise InvalidException(f"Already installed: {self._name}")

        # Create the resource in the database
        self._res_id = DB.set_res(
            self._tsk_id, name=self._name, action=self._action,
            arguments=self._arguments)

        # Do action
        self._do_action(submit, force)

    def _remove(self, submit):
        """
        Remove an existing resource.

        Args:
            submit (function): Task executor submit function.
        """
        if not self._res_id:
            raise InvalidException(f"Not installed: {self._name}")

        futures = list()
        add_future = futures.append
        remove_src = self._remove_src

        # Remove source and destinations
        for src_row in DB.get_src_by_res(res_id=self._res_id):
            add_future(submit(remove_src, src_row['id']))

        # Wait for completion
        for future in futures:
            future.result()

        # Remove resource
        DB.del_res(self._res_id)

    def _update(self, submit, force=False):
        """
        Update an existing resource

        Args:
            submit (function): Task executor submit function.
            force (bool): If True, force operation.
        """
        if not self._res_id:
            raise InvalidException(f"Not installed: {self._name}")

        # Do action
        self._do_action(submit, force, update=True)

        # Update last Task ID on resource
        DB.set_res(self._tsk_id, res_id=self._res_id)

    def _do_action(self, submit, force, update=False):
        """
        Do the resource action.

        Args:
            submit (function): Task executor submit function.
            force (bool): If True, force operation.
            update (bool): If True, task is an update.
        """
        src_futures = dict()

        # Do action on resource sources
        for src in get_plt(self._name).get_src_list(self._name, self._res_id):
            src_futures[src] = future = submit(
                getattr(src, self._action), update=update, tsk_id=self._tsk_id,
                force=force, **self._arguments)
            future.add_done_callback(src.set_done_callback)

        # Wait all write operations completion before start deletion operations
        for future in src_futures.values():
            future.result()

        # Remove orphans destinations
        src_ids = set()
        futures = list()
        add_future = futures.append
        add_src_id = src_ids.add
        for src in src_futures:
            add_future(submit(src.remove_orphans))
            add_src_id(src.src_id)

        # Remove orphans sources
        remove_src = self._remove_src
        for src_row in DB.get_src_by_res(res_id=self._res_id):
            if src_row['id'] not in src_ids:
                add_future(submit(remove_src, src_row['id']))

        # Wait for completion
        for future in futures:
            future.result()

    @staticmethod
    def _remove_src(src_id):
        """
        Fully remove a source and all associated destinations.

        Args:
            src_id (int): Source ID.
        """
        for dst_row in DB.get_dst_by_src(src_id):
            remove_existing(dst_row['path'])
        DB.del_src(src_id)
