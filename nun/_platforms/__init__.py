"""Platforms"""

from abc import ABC, abstractmethod
from json import load, dump
from importlib import import_module
from os.path import join
from threading import Lock

from requests import Session

from nun._config import CONFIG_DIR

_PLATFORMS = dict()
_PLATFORMS_LOCK = Lock()


def get_files(resource, task_id):
    """
    Get files of a resource.

    Args:
        resource (str): Resource.
        task_id (int): Task ID.

    Returns:
        list of nun._files.FileBase subclass instance: Files
    """
    scheme, path = resource.split('://', 1)

    with _PLATFORMS_LOCK:
        # Get cached platform
        try:
            platform = _PLATFORMS[scheme]

        # Or, instantiate the platform and cache it
        except KeyError:
            platform = _PLATFORMS[scheme] = import_module(
                f'{__name__}.{scheme}').Platform()

    # Get files
    return platform.get_files(path, task_id)


class PlatformBase(ABC):
    """
    Platform base class.
    """
    __slots__ = ('_http_request', '_http_session')

    def __init__(self):
        self._http_session = Session()
        self._http_request = self._http_session.request

    @abstractmethod
    def autocomplete(self, partial_resource):
        """
        Autocomplete resource ID.

        Args:
            partial_resource (str): Partial resource.

        Returns:
            list of str: Resource candidates.
        """

    def request(self, url, method='GET', ignore_status=None, **kwargs):
        """
        Performs a request.

        Args:
            method (str): Request method. Default to "GET".
            url (str): URL.
            ignore_status (tuple of int): Does not raise exceptions on theses
                status.
            kwargs: requests.Session.request keyword arguments

        Returns:
            requests.Response: Response.
        """
        # TODO: Add automatic retries for common return codes (
        #       408, 500, 502, 504)
        response = self._http_request(method, url, **kwargs)
        if ignore_status and response.status_code not in ignore_status:
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

    def get_files(self, resource, task_id):
        """
        Get files of a specific resource.

        Args:
            resource (str): Resource.
            task_id (int): Task ID.

        Returns:
            list of nun._files.FileBase: Files.
        """
        return list(self._get_files(resource, task_id))

    @abstractmethod
    def _get_files(self, resource, task_id):
        """
        Get files of a specific resource.

        Args:
            resource (str): Resource.
            task_id (int): Task ID.

        Returns:
            generator of nun._files.FileBase: Files.
        """

    @abstractmethod
    def exception_handler(self, resource, name=None, status=404):
        """
        Handle exception to return clear error message.

        Args:
            resource (str): Resource ID.
            status (int): Status code. Default to 404.
            name (str): Resource name override

        Raises:
            FileNotFoundError: Not found.
        """
