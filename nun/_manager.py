# coding=utf-8
"""
Manager
"""
from importlib import import_module
from concurrent.futures import ThreadPoolExecutor

from requests import Session

from nun._platforms import __name__ as platform_module
from nun._output import __name__ as output_module, OutputBase
from nun._cache import clear_cache


class Manager:
    """Package manager"""
    __slots__ = ('_resources_ids', '_resources', '_track', '_http_session',
                 '_platforms', '_action_kwargs', '_width', '_clear', '_output',
                 '_debug')

    #: Output type, set externally
    OUTPUT = None

    def __init__(self, resources_ids, no_track=False, debug=False,
                 **action_kwargs):
        self._debug = debug
        self._resources_ids = resources_ids
        self._resources = None
        self._track = not no_track
        self._http_session = None
        self._platforms = dict()
        self._action_kwargs = action_kwargs

        # Initializes output
        if self.OUTPUT:
            self._output = import_module(
                f'{output_module}.{self.OUTPUT}').Output()
        else:
            # No output
            self._output = OutputBase()

    @property
    def output(self):
        """
        Return output.

        Returns:
            nun._output.OutputBase subclass instance: output.
        """
        return self._output

    def get_platform(self, name):
        """
        Get a platform by name.

        Args:
            name (str): Platform name.

        Returns:
            nun._platforms.ResourceBase subclass instance: Resource
        """
        # Get cached platform
        try:
            return self._platforms[name]

        # Or, instantiate the platform and cache it
        except KeyError:
            self._platforms[name] = import_module(
                f'{platform_module}.{name}').Platform(self)
            return self._platforms[name]

    @property
    def resources(self):
        """
        Resources.

        Returns:
            list of nun._platforms.ResourceBase subclass instance: Resources
        """
        if self._resources is None:
            self._resources = list()
            add_resource = self._resources.append
            for resource_id in set(self._resources_ids):
                scheme, path = resource_id.split('://', 1)
                add_resource(self.get_platform(scheme).get_resource(path))
        return self._resources

    def perform(self, action):
        """
        Perform action on files
        """
        # Generated tasks
        # TODO: Check if up to date before generating tasks
        files = {}
        with ThreadPoolExecutor() as executor:
            for resource in self.resources:
                for file in resource.files:
                    future = executor.submit(
                        getattr(file, action), **self._action_kwargs)
                    future.add_done_callback(file.set_done_callback)
                    files[file] = future

            # Wait for completion and show progress
            self._output.show_progress(files)

        failed = []
        for file, future in files.items():
            try:
                destinations = future.result()
            except Exception:
                # Tasks processing exceptions are handled by output
                if self._output and not self._debug:
                    failed.append(file)
                    continue
                raise

            # Track changes
            if self._track:
                pass
                # TODO: Track changes "destinations"
                # TODO: remove files that where removed between previous version

        # Raise exception globally for all tasks
        if failed:
            raise RuntimeError(
                'Failures:\n - ' +
                '\n - '.join(f'{file.resource_id}, {file.name}'
                             for file in failed))

    @property
    def http_session(self):
        """
        HTTP session.

        Returns:
            requests.Session: HTTP session.
        """
        # Lazy import, may no always be required
        if self._http_session is None:
            self._http_session = Session()
        return self._http_session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_cache()
