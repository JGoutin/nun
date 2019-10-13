"""Platforms"""
# TODO:
#  - bitbucket
#  - gitlab
#  - git (Any git over internet)
#  - http (any single file over internet)

from abc import ABC, abstractmethod
from json import load, dump
from os.path import join

from nun._files import FileBase
from nun._config import CONFIG_DIR


class PlatformBase(ABC):
    """
    Platform base class.

    Args:
        manager (nun._manager.Manager): HTTP session.
    """
    __slots__ = ('_manager', '_http_request')

    def __init__(self, manager):
        self._manager = manager
        self._http_request = None

    @abstractmethod
    def get_resource(self, resource_id):
        """
        Resource.

        Args:
            resource_id (str): Resource ID.

        Returns:
            nun._platforms.ResourceBase subclass instance: Resource
        """

    @abstractmethod
    async def autocomplete(self, partial_resource_id):
        """
        Autocomplete resource ID.

        Args:
            partial_resource_id (str): Partial resource ID.

        Returns:
            list of str: Resource ID candidates.
        """

    async def request(self, url, method='GET', ignore_status=None, **kwargs):
        """
        Performs a request.

        Args:
            method (str): Request method. Default to "GET".
            url (str): URL.
            ignore_status (tuple of int): Does not raise exceptions on theses
                status.
            kwargs: aiohttp.client.ClientSession.request keyword arguments

        Returns:
            aiohttp.client_reqrep.ClientResponse: Response.
        """
        if self._http_request is None:
            self._http_request = self._manager.http_session.request

        # TODO: Add automatic retries for common return codes (
        #       408, 500, 502, 504)
        response = await self._http_request(method, url, **kwargs)
        if ignore_status and response.status not in ignore_status:
            response.raise_for_status()

        return response

    @classmethod
    def _get_secret(cls, name):
        """
        Get a secret from OS keyring.

        Args:
            name (str): Secret name.

        Returns:
            str or None: Secret value.
        """
        # Use OS keyring if possible
        try:
            from keyring import get_password
            return get_password(cls.__module__, name)

        # Use local file if not in configuration directory
        except ImportError:
            from hashlib import blake2b
            try:
                with open(join(CONFIG_DIR, 'store'), 'rt') as store_json:
                    return load(store_json).get(
                        blake2b(name.encode(), digest_size=32).hexdigest())
            except FileNotFoundError:
                return

    @classmethod
    def _set_secret(cls, name, value):
        """
        Set a secret in OS keyring.

        Args:
            name (str): Secret name.
            value (str): Secret value.
        """
        # Use OS keyring if possible
        try:
            from keyring import set_password
            set_password(cls.__module__, name, value)

        # Use local file if not in configuration directory
        except ImportError:
            from hashlib import blake2b
            try:
                with open(join(CONFIG_DIR, 'store'), 'rt') as store_json:
                    store = load(store_json)
            except FileNotFoundError:
                store = dict()

            store[blake2b(name.encode(), digest_size=32).hexdigest()] = value
            with open(join(CONFIG_DIR, 'store'), 'wt') as store_json:
                dump(store, store_json)
            return


class ResourceBase(ABC):
    """
    Platform base class.

    Args:
        platform (nun._platforms.PlatformBase subclass instance): Platform
        resource_id (str): Resource ID.
    """
    __slots__ = ('_platform', '_resource_id')

    def __init__(self, platform, resource_id):
        self._platform = platform
        self._resource_id = resource_id

    @property
    def platform(self):
        """
        Platform.

        Returns:
            nun._platforms.PlatformBase subclass instance: Platform
        """
        return self._platform

    @property
    def resource_id(self):
        """
        Resource ID.

        Returns:
            str: Resource ID.
        """
        return self._resource_id

    @property
    @abstractmethod
    async def info(self):
        """
        Reference information.

        Returns:
            dict: Information.
        """

    @property
    @abstractmethod
    async def version(self):
        """
        Resource version.

        Returns:
            str: Version.
        """

    @property
    async def files(self):
        """
        Files of this resource.

        Returns:
            async generator of nun._files.FileBase: Files.
        """
        async for name, url in self._get_files():
            yield FileBase(name, url, self)

    @abstractmethod
    async def _get_files(self):
        """
        Files of this resource.

        Returns:
            async generator of tuple: name, url.
        """
        yield

    @abstractmethod
    async def exception_handler(self, status=404, res_name=None):
        """
        Handle exception to return clear error message.

        Args:
            status (int): Status code. Default to 404.
            res_name (str): Resource name. If not specified, use stored resource
                name.

        Raises:
            FileNotFoundError: Not found.
        """
