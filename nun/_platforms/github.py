"""GitHub"""
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from fnmatch import fnmatch
from asyncio import create_task, sleep

from nun._platforms import PlatformBase, ResourceBase
from nun._cache import get_cache, set_cache

GITHUB = 'https://github.com'
GITHUB_API = 'https://api.github.com'
GITHUB_RAW = 'https://raw.githubusercontent.com'


class Platform(PlatformBase):
    """
    GitHub platform.
    """
    _GITHUB_API_HEADERS = None
    _RATE_LIMIT_WARNED = False

    def get_resource(self, resource_id):
        """
        GitHub resource.

        Args:
            resource_id (str): Resource ID.

        Returns:
            Resource: nun._platforms.github.Resource
        """
        return Resource(self, resource_id)

    async def autocomplete(self, partial_resource_id):
        """
        Autocomplete resource ID.

        Args:
            partial_resource_id (str): Partial resource ID.

        Returns:
            list of str: Resource ID candidates.
        """
        # TODO: implement, see _list_refs, _list_repos
        return []

    @staticmethod
    def _parse_resource_id(resource_id):
        """
        Parse the resource ID in format: "owner/repo/ref[/resource]"

        "owner" is the repository name of the user or organization owning the
        repository on GitHub.

        "repo" is the repository name on GitHub.

        "ref" can be a GitHub release tag, a Git tag, a Git branch or
        a Git commit.

        "resource" can be "tarball", "zipball", a GitHub release asset filename
        or the relative path or a file present in the Git repository.
        If not specified, default to "tarball".

        Args:
            resource_id (str): Resource ID.

        Returns:
            tuple: owner, repo, reference, resource
        """
        try:
            owner, repo, ref, resource = resource_id.split('/', 3)
        except ValueError:
            owner, repo, ref = resource_id.split('/', 2)
            resource = 'tarball'  # Default to tarball if not specified

        return owner, repo, ref if ref != 'latest' else None, resource

    @classmethod
    def _api_headers(cls, modified_since=None):
        """
        Return headers to use to make requests to GitHub API.

        Args:
            modified_since (str): "If-Modified-Since" header date.

        Returns:
            dict or None: API request headers.
        """
        # Create headers base with authentication if token provided
        if cls._GITHUB_API_HEADERS is None:
            auth_headers = {}
            token = cls._get_secret('token')
            if token:
                auth_headers["Authorization"] = f"token {token}"
            cls._GITHUB_API_HEADERS = auth_headers

        # Add If-Modified-Since to perform API Conditional requests
        if modified_since:
            headers = cls._GITHUB_API_HEADERS.copy()
            headers['If-Modified-Since'] = modified_since
            return headers

        return cls._GITHUB_API_HEADERS

    async def _github_api(self, path):
        """
        Make a get request to the Github REST API.
        https://developer.github.com/v3/

        Args:
            path (str): GitHub API path.

        Returns:
            tuple: response dict, status
        """
        # Retrieve request from cache
        try:
            result, date, status = await get_cache(path)
        except TypeError:
            result = date = status = None

        # Return cached result directly if younger 60 seconds
        if date:
            dt_date = parsedate_to_datetime(date)
            if dt_date > datetime.now(dt_date.tzinfo) - timedelta(seconds=10):
                return result, status

        # Perform requests
        while True:
            resp = await self.request(
                GITHUB_API + path,
                headers=self._api_headers(modified_since=date),
                ignore_status=(403, 404))

            if resp.status == 403:
                # API Rate limit reached, wait ready and retry
                if int(resp.headers.get('X-RateLimit-Remaining', '-1')) == 0:
                    await self._wait_rate_limit()
                    continue

                # Other permission error, raise
                resp.raise_for_status()
            break

        # Return cached result if no changes since last request
        if resp.status == 304:
            return result, status

        # Cache and return current request result
        status = resp.status
        result = await resp.json()
        await set_cache(path, [result, resp.headers['Date'], status],
                        long=resp.status < 400)
        return result, status

    async def _wait_rate_limit(self):
        """
        Wait until remaining rate limit is greater than 0.
        """
        while True:
            # Warn user.
            if not self._RATE_LIMIT_WARNED:
                msg = 'GitHub rate limit reached, waiting...'
                if 'Authorization' not in self._GITHUB_API_HEADERS:
                    msg += (
                        ' Authenticate with your GitHub account to increase the'
                        ' rate limit.')
                    # TODO: explain how use GitHub account
                self._manager.output.warn(msg)
                self._RATE_LIMIT_WARNED |= True

            # Wait until rate limit API return remaining > 0
            await sleep(60)
            resp = await self.request(
                GITHUB_API + '/rate_limit', headers=self._api_headers())
            if int((await resp.json())['resources']['core']['remaining']):
                return

    async def _exists(self, path, condition):
        """
        Check if path returns 404 status.

        Args:
            path (str): GitHub API path.
            condition (bool-like object): If False, assume not exists.

        Returns:
            bool: True if exist.
        """
        if condition:
            return (await self._github_api(path))[1] != 404
        return False

    async def _handle_404(self, owner, repo=None, ref=None, res=None,
                          status=404):
        """
        Try to find exactly what is the missing object an raise exception.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name
            ref (str): Reference.
            res (str): Resource.
            status (int): HTTP status code.

        Raises:
            FileNotFoundError: Not found.
        """
        if status != 404:
            return

        # Owner, cannot exist if no repository specified.
        org_task = create_task(
            self._exists(f'/orgs/{owner}', owner and repo))
        user_task = create_task(
            self._exists(f'/users/{owner}', owner and repo))

        # Repository, cannot exist if no ref specified.
        repo_task = create_task(
            self._exists(f'/repos/{owner}/{repo}', repo and ref))

        # Reference, cannot exist if ref is specified.
        ref_task = create_task(
            self._exists(f'/repos/{owner}/{repo}/git/trees/{ref}', ref and res))

        owner_exists = (await org_task) or (await user_task)
        repo_exists = await repo_task & owner_exists
        ref_exists = await ref_task & repo_exists

        if ref_exists:
            raise FileNotFoundError(
                f'No GitHub resource "{res}" found for "{owner}/{repo}:{ref}"')

        elif repo_exists:
            raise FileNotFoundError(
                f'No GitHub reference "{ref}" found for "{owner}/{repo}"')

        elif owner_exists:
            raise FileNotFoundError(
                f'No GitHub repository "{repo}" found for "{owner}"')

        else:
            raise FileNotFoundError(
                f'No GitHub user or organization "{owner}" found"')

    async def _list_refs(self, owner, repo, tags=False, branches=False):
        """
        List references for specified repository.
        By default, list only GitHub releases.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name
            tags (bool): If True, list also Git tags.
            branches (bool): IF True, list also Git branches.

        Returns:
            list of dict: References.
        """
        # Perform requests
        releases_task = create_task(
            self._github_api(f'/repos/{owner}/{repo}/releases'))
        if tags:
            tags_task = create_task(
                self._github_api(f'/repos/{owner}/{repo}/tags'))
        if branches:
            branches_task = create_task(
                self._github_api(f'/repos/{owner}/{repo}/branches'))

        # Retrieves results
        refs = list()
        add_ref = refs.append

        releases, status = await releases_task
        await self._handle_404(owner, repo, status=status)

        for release in releases:
            add_ref(dict(
                ref=release['tag_name'], type='release', desc=release['name']))

        if tags:
            for tag in (await tags_task)[0]:
                add_ref(dict(type='tag', ref=tag['name']))

        if branches:
            for branch in (await branches_task)[0]:
                add_ref(dict(type='branch', ref=branch['name']))

        return refs

    async def _list_repos(self, owner):
        """
        List repositories for the specified owner.

        Args:
            owner (str): Repository owner.

        Returns:
            list of str: Repositories names.
        """
        org_task = create_task(self._github_api(f'/orgs/{owner}/repos'))
        user_task = create_task(self._github_api(f'/users/{owner}/repos'))

        resp, status = await org_task
        if status != 404:
            user_task.cancel()
            return [repo['name'] for repo in resp['result']]

        resp, status = await user_task
        if status != 404:
            return [repo['name'] for repo in resp['result']]

        await self._handle_404(owner)


class Resource(ResourceBase):
    """
    GitHub resource.

    Args:
        platform (nun._platforms.github.Platform): GitHub platform.
        resource_id (str): Resource ID.
    """
    __slots__ = ('_github_api', '_owner', '_repo', '_ref_name',
                 '_ref_type', '_ref_info', '_ref_hash', '_ref_assets', '_res')

    def __init__(self, platform, resource_id):
        ResourceBase.__init__(self, platform, resource_id)

        self._github_api = platform._github_api
        self._owner, self._repo, self._ref_name, self._res = \
            self._platform._parse_resource_id(resource_id)

        self._ref_type = None
        self._ref_info = None
        self._ref_hash = None
        self._ref_assets = None

    @property
    async def info(self):
        """
        Reference information.

        Returns:
            dict: Information.
        """
        # Special case of reference set to latest branch by default
        if self._ref_info is None and self._ref_type == 'branch':
            resp, status = await self._github_api(
                f'/repos/{self._owner}/{self._repo}/branches/{self._ref_name}')
            await self.exception_handler(status=status)
            self._ref_info = resp

        # Requires full update in any other cases
        elif self._ref_info is None:
            await self._update_reference()

        # TODO: Filter useful information
        return self._ref_info

    @property
    async def version(self):
        """
        Resource version.
        The Commit Hash is used as version on GitHub.

        Returns:
            str: Version.
        """
        if self._ref_hash is None:
            resp, status = await self._github_api(
                f'/repos/{self._owner}/{self._repo}/git/trees/'
                f'{self._ref_name}')
            await self.exception_handler(status=status)
            self._ref_hash = resp['sha']

        return self._ref_hash

    async def _get_files(self):
        """
        Files of this resource.

        Returns:
            async generator of tuple: name, url.
        """
        # Ensure reference name is set
        await self._update_reference_name()

        # Archives
        # TODO: Preselect file format to use since known in advance
        if self._res in ('zipball', 'tarball'):
            yield (f'{self._owner}-{self._repo}-{self._ref_name}.'
                   f'{"zip" if self._res == "zipball" else "tar.gz"} ',
                   f'{GITHUB}/{self._owner}/{self._repo}/'
                   f'{self._res}/{self._ref_name}')
            return

        # Release assets
        if self._ref_assets is None:
            await self._update_reference()

        yield_assets = False
        for asset in self._ref_assets:
            if fnmatch(asset['name'], self._res):
                yield asset['name'], asset['browser_download_url']
                yield_assets = True
        if yield_assets:
            return

        # Raw file
        # TODO: Get Git tree and apply fnmatch on it
        #       /repos/:owner/:repo/git/trees/:tree_sha
        #       /repos/:owner/:repo/git/trees/:tree_sha?recursive=1
        yield (self._res, f'{GITHUB_RAW}/{self._owner}/{self._repo}/'
                          f'{self._ref_name}/{self._res}')

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
        await self._platform._handle_404(
            self._owner, self._repo, self._ref_name, res_name or self._res,
            status=status)

    async def _update_reference_name(self):
        """
        Reference.
        """
        if self._ref_name:
            return

        # If not specified, default to latest version
        release_task = create_task(self._github_api(
            f'/repos/{self._owner}/{self._repo}/releases/latest'))
        branch_task = create_task(self._github_api(
            f'/repos/{self._owner}/{self._repo}'))

        # Get latest stable GitHub release
        resp, status = await release_task
        if status != 404:
            branch_task.cancel()
            self._ref_type = 'release'
            self._ref_name = resp['tag_name']
            self._ref_assets = resp['assets']
            self._ref_info = resp

        # If no release, Get default Git branch
        else:
            resp, status = await branch_task
            await self.exception_handler(status=status)
            self._ref_type = 'branch'
            self._ref_assets = ()
            self._ref_name = resp['default_branch']

    async def _update_reference(self):
        """
        Update reference type, info and assets.
        """
        # Ensure reference name is set
        await self._update_reference_name()

        # If reference type is not specified, require to find it before anything
        release_task = create_task(self._github_api(
            f'/repos/{self._owner}/{self._repo}/releases/tags/{self._ref_name}'
        ))
        branch_task = create_task(self._github_api(
            f'/repos/{self._owner}/{self._repo}/branches/{self._ref_name}'))
        tag_task = create_task(self._github_api(
            f'/repos/{self._owner}/{self._repo}/git/refs/tags/{self._ref_name}'
        ))
        commit_task = create_task(self._github_api(
            f'/repos/{self._owner}/{self._repo}/commits/{self._ref_name}'))

        resp, status = await release_task
        if status != 404:
            # Reference is a GitHub release
            branch_task.cancel()
            commit_task.cancel()
            tag_task.cancel()
            self._ref_type = 'release'
            self._ref_assets = resp['assets']
            self._ref_info = resp
            return

        resp, status = await branch_task
        if status != 404:
            # Reference is a Git branch
            commit_task.cancel()
            tag_task.cancel()
            self._ref_type = 'branch'
            self._ref_assets = ()
            self._ref_hash = resp['commit']['sha']
            self._ref_info = resp
            return

        resp, status = await tag_task
        if status != 404:
            # Reference is a Git tag
            commit_task.cancel()
            self._ref_type = 'tag'
            self._ref_assets = ()
            self._ref_hash = resp['object']['sha']
            self._ref_info = resp
            return

        resp, status = await commit_task
        if status != 404:
            # Reference is a Git commit
            self._ref_type = 'commit'
            self._ref_assets = ()
            self._ref_hash = resp['sha']
            self._ref_info = resp
            return

        await self.exception_handler()
