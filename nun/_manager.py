"""
Manager
"""
from asyncio import create_task
from importlib import import_module

#import aiosqlite

from nun._platforms import __name__ as platform_module
from nun._output import __name__ as output_module, OutputBase
from nun._cache import clear_cache


class Manager:
    """Package manager"""
    __slots__ = ('_resources_ids', '_resources', '_track', '_http_session',
                 '_platforms', '_action_kwargs', '_width', '_clear', '_output')

    #: Output type, set externally
    OUTPUT = None

    def __init__(self, resources_ids, no_track=False, **action_kwargs):
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

    async def download(self):
        """
        Download files
        """
        # TODO: Make this global for download, extract...

        # Generated tasks
        # TODO: Check if up to date before generating tasks
        files = []
        add_file = files.append
        for resource in self.resources:
            async for file in resource.files:
                task = create_task(file.download(**self._action_kwargs))
                file.set_task(task)
                add_file(file)

        progress = create_task(self._output.show_progress(files))

        # Wait for completion
        failed = []
        for file in files:
            try:
                await file.task
            except Exception:
                # Tasks processing exceptions are handled by output
                if self._output:
                    failed.append(file)
                    continue
                raise

            # Track changes
            if self._track:
                new_files = file.task.result()
                # TODO: Track changes
                # TODO: remove files that where removed between previous version

        await progress

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
            aiohttp.client.ClientSession: HTTP session.
        """
        # Lazy import, may no always be required
        if self._http_session is None:
            from aiohttp import ClientSession
            self._http_session = ClientSession()
        return self._http_session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        clear_cache()
        try:
            await self._http_session.close()
        except AttributeError:
            pass
