# coding=utf-8
"""
Manager
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from json import loads
from time import sleep

from nun._platforms import get_files
from nun._output import get_output
from nun._cache import clear_cache
from nun._database import DB
from nun._destination import remove_existing


class Manager:
    """Package manager"""
    __slots__ = ('_resources', '_http_session', '_action',
                 '_action_kwargs', '_output', '_debug',)

    #: Output type, set externally
    OUTPUT = None

    def __init__(self, resources, action, debug=False, **action_kwargs):
        self._debug = debug
        self._resources = resources
        self._http_session = None
        self._action = action
        self._action_kwargs = action_kwargs
        self._output = get_output(self.OUTPUT)

    def _get_tasks(self):
        """
        Return all tasks in database matching "ressource".

        Returns:
            dict: Matching tasks
        """
        tasks = {}
        if self._action in ('update', 'remove'):
            # Use glob pattern matching
            for resource in set(self._resources):
                for row in DB.get_tasks(resource):
                    tasks[row.resource] = row
        else:
            # Use exact matching
            for resource in set(self._resources):
                row = DB.get_tasks(resource)
                if row:
                    tasks[resource] = row
        return tasks

    def _submit_write_actions(self, submit, db_tasks, transaction_id):
        """
        Get remotes files for resources.

        Args:
            submit (function): Executor submit function.
            db_tasks (dict): Tasks from database.
            transaction_id (int): Transaction ID.

        Returns:
            dict: Future files per task ID.
        """
        # Skipping when removing
        if self._action == 'remove':
            return list()

        # Update, must use previous action and arguments
        if self._action == 'update':
            update = True
            action = None
            action_kwargs = None

        # New files
        else:
            action = self._action
            action_kwargs = self._action_kwargs
            update = False

        # Get files lists
        get_files_futures = dict()
        for resource in set(self._resources):
            try:
                task_id = db_tasks[resource]['id']
            except KeyError:
                if update:
                    # TODO: Warn user, can only update already in database
                    continue
                task_id = DB.set_task(
                    transaction_id, resource=resource, action=action,
                    arguments=action_kwargs)
            else:
                if not update:
                    # TODO: Warn user, already installed
                    continue
            get_files_futures[submit(get_files, resource, task_id)] = task_id

        # Start files operations
        tasks_in_progress = dict()
        for get_files_future in as_completed(get_files_futures):
            task_id = get_files_futures[get_files_future]
            files = tasks_in_progress[task_id] = dict()
            for file in get_files_future.result():
                if update:
                    task = db_tasks[task_id]
                    action = task.action
                    action_kwargs = loads(task.action_kwargs)
                future = submit(getattr(file, action), update=update,
                                transaction_id=transaction_id, **action_kwargs)
                future.add_done_callback(file.set_done_callback)
                files[future] = file

        return tasks_in_progress

    def _submit_remove_actions(self, submit, tasks_in_progress):
        """
        Get remotes files for resources.

        Args:
            submit (function): Executor submit function.
            tasks_in_progress (dict): Tasks in progress.
        """
        # Only wait for completion
        if self._action not in ('update', 'remove'):

            for future_files in tasks_in_progress:
                for future in future_files:
                    future.result()
            return

        # Trigger deletion
        futures = list()
        futures_append = futures.append
        completed = set()
        while True:
            sleep(0.25)
            for future_files, task_id in tasks_in_progress.items():
                # Wait for completion of write tasks and check results
                if not all(file.done for file in future_files.values()):
                    continue

                completed.add(task_id)
                for future in future_files:
                    future.result()

                # Get obsoletes destinations from database
                files = {file.file_id: file for file in future_files.values()}

                for file_row in DB.get_files(task_id):
                    file_id = file_row['id']
                    try:
                        file = files[file_id]

                    except KeyError:
                        # File not in transaction are outdated
                        futures_append(submit(self._remove_file, file_id))

                    else:
                        # File changed, destinations that were not updated or
                        # checked are outdated
                        if file.destinations is not None:
                            futures_append(submit(
                                self._remove_orphan, file, file_id))

            if len(completed) == len(tasks_in_progress):
                break

        # Wait for deletion
        for future in futures:
            future.result()

    @staticmethod
    def _remove_orphan(file):
        """
        Remove all orphaned destinations of a file.

        Args:
            file (nun._files.FileBase): File.
        """
        dests = file.destinations
        for dest_row in DB.get_destinations(file.file_id):
            if dest_row['id'] not in dests:
                remove_existing(dest_row['path'])
                DB.del_destination(dest_row['id'])

    @staticmethod
    def _remove_file(file_id):
        """
        Remove a file and all associated destinations.

        Args:
            file_id (int): File ID in database.
        """
        for row in DB.get_destinations(file_id):
            remove_existing(row['path'])
        DB.del_file(file_id)

    def perform(self):
        """
        Perform action on files
        """
        transaction_id = DB.set_transaction()

        # List resources
        with ThreadPoolExecutor() as executor:
            submit = executor.submit

            # Get tasks from database
            tasks = self._get_tasks()

            # Submit file operation for files that requires update
            tasks_in_progress = self._submit_write_actions(
                submit, tasks, transaction_id)

            # Submit remove
            self._submit_remove_actions(submit, tasks_in_progress)

            # Clean up tasks
            if self._action == 'remove':
                for task_id in tasks_in_progress:
                    DB.del_task(task_id)

            # Wait for completion and show progress
            # TODO: handle progress
            #self._output.show_progress()

        # TODO: handle failures
        failed = []
        # for file, future in files.items():
        #    try:
        #        future.result()
        #    except Exception:
        #        # Tasks processing exceptions are handled by output
        #        if self._output and not self._debug:
        #            failed.append(file)
        #            continue
        #        raise

        # Raise exception globally for all tasks
        if failed:
            raise RuntimeError('Failures:\n - ' + '\n - '.join(
                f'{file.resource}, {file.name}' for file in failed))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_cache()
