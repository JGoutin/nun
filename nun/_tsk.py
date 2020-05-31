"""
Task
"""
from concurrent.futures import ThreadPoolExecutor
from nun._db import DB
from nun._ui import get_ui
from nun._srg import clear_cache
from nun._res import Res


class Tsk:
    """Task"""

    __slots__ = (
        "_res_names",
        "_action",
        "_arguments",
        "_ui",
        "_debug",
        "_tsk_id",
        "_force",
    )

    def __init__(self, res_names, action, debug=False, force=False, **arguments):
        self._debug = debug
        self._force = force
        self._tsk_id = DB.set_tsk()
        self._res_names = set(res_names)
        self._action = action
        self._arguments = arguments
        self._ui = get_ui()

    def apply(self):
        """
        Apply task
        """
        # TODO: Ensure re-applying is idempotent
        # TODO: handle failures
        # TODO: UI progress

        tsk_id = self._tsk_id
        action = self._action
        force = self._force

        # Get resources
        if action in ("update", "remove"):
            # Existing resources from database with glob pattern
            resources = (
                Res(
                    tsk_id=tsk_id,
                    res_id=row["id"],
                    name=row["name"],
                    action=row["action"],
                    arguments=row["arguments"],
                )
                for glob in self._res_names
                for row in DB.get_res_by_glob(glob)
            )

        else:
            # New resources
            arguments = self._arguments
            resources = (
                Res(tsk_id=tsk_id, name=name, action=action, arguments=arguments)
                for name in self._res_names
            )

        # Perform action on each resource
        dsts = dict()  # TODO: use it to check for conflics while applying
        futures = list()
        add_future = futures.append
        with ThreadPoolExecutor() as executor:
            submit = executor.submit

            for res in resources:
                add_future(submit(res.apply, action, submit, force))

            # Wait for completion
            for future in futures:
                future.result()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_cache()
