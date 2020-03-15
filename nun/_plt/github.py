"""GitHub"""
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from fnmatch import fnmatch
from time import sleep

from requests import Session

from nun._plt import PltBase
from nun._srg import get_cache, set_cache, get_secret
from nun._src import get_src
from nun.exceptions import NotFoundException

GITHUB = 'https://github.com'
GITHUB_API = 'https://api.github.com'
GITHUB_RAW = 'https://raw.githubusercontent.com'


class Plt(PltBase):
    """
    GitHub platform.
    """
    _GITHUB_API_HEADERS = None
    _RATE_LIMIT_WARNED = False

    __slots__ = ('_http_request', '_http_session')

    def __init__(self):
        self._http_session = Session()
        self._http_request = self._http_session.request

    @staticmethod
    def _parse_res_name(res_name):
        """
        Parse the resource ID in format: "github://owner/repo/ref[/source]"

        "owner" is the repository name of the user or organization owning the
        repository on GitHub.

        "repo" is the repository name on GitHub.

        "ref" can be a GitHub release tag, a Git tag, a Git branch or
        a Git commit.

        "source" can be "tarball", "zipball", a GitHub release asset filename
        or the relative path or a file present in the Git repository.
        If not specified, default to "tarball".

        Args:
            res_name (str): Resource name.

        Returns:
            tuple: owner, repo, reference, source
        """
        try:
            owner, repo, ref, src = res_name.split('://', 1)[1].split('/', 3)
        except ValueError:
            owner, repo, ref = res_name.split('/', 2)
            src = 'tarball'  # Default to tarball if not specified

        return owner, repo, ref if ref != 'latest' else None, src

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
            token = get_secret(f'{cls.__module__}.token')
            if token:
                auth_headers["Authorization"] = f"token {token}"
            cls._GITHUB_API_HEADERS = auth_headers

        # Add If-Modified-Since to perform API Conditional requests
        if modified_since:
            headers = cls._GITHUB_API_HEADERS.copy()
            headers['If-Modified-Since'] = modified_since
            return headers

        return cls._GITHUB_API_HEADERS

    def _request(self, url, method='GET', ignore_status=None, **kwargs):
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
        response = self._http_request(method, url, **kwargs)
        if ignore_status and response.status_code not in ignore_status:
            response.raise_for_status()

        return response

    def _github_api(self, path):
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
            result, date, status = get_cache(path)
        except TypeError:
            result = date = status = None

        # Return cached result directly if younger 60 seconds
        if date:
            dt_date = parsedate_to_datetime(date)
            if dt_date > datetime.now(dt_date.tzinfo) - timedelta(seconds=10):
                return result, status

        # Perform requests
        while True:
            resp = self._request(
                GITHUB_API + path,
                headers=self._api_headers(modified_since=date),
                ignore_status=(403, 404))

            if resp.status_code == 403:
                # API Rate limit reached, wait ready and retry
                if int(resp.headers.get('X-RateLimit-Remaining', '-1')) == 0:
                    self._wait_rate_limit()
                    continue

                # Other permission error, raise
                resp.raise_for_status()
            break

        # Return cached result if no changes since last request
        if resp.status_code == 304:
            return result, status

        # Cache and return current request result
        status = resp.status_code
        result = resp.json()
        set_cache(path, [result, resp.headers['Date'], status],
                  long=resp.status_code < 400)
        return result, status

    def _wait_rate_limit(self):
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
                    # TODO: Warn + explain how use GitHub account
                self._RATE_LIMIT_WARNED |= True

            # Wait until rate limit API return remaining > 0
            sleep(60)
            resp = self._request(
                GITHUB_API + '/rate_limit', headers=self._api_headers())
            if int((resp.json())['resources']['core']['remaining']):
                return

    def _exists(self, path, condition):
        """
        Check if path returns 404 status.

        Args:
            path (str): GitHub API path.
            condition (bool-like object): If False, assume not exists.

        Returns:
            bool: True if exist.
        """
        if condition:
            return (self._github_api(path))[1] != 404
        return False

    def _raise_not_found(self, owner, repo=None, ref=None, src=None):
        """
        Try to find exactly what is the missing object and raise exception.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name
            ref (str): Reference.
            src (str): Source.

        Raises:
            nun.exceptions.NotFoundException: Not found.
        """
        # Owner, cannot exist if no repository specified.
        owner_exists = self._exists(
            f'/orgs/{owner}', owner and repo) or self._exists(
            f'/users/{owner}', owner and repo)

        # Repository, cannot exist if no ref specified.
        repo_exists = self._exists(
            f'/repos/{owner}/{repo}', repo and ref) & owner_exists

        # Reference, cannot exist if ref is specified.
        ref_exists = self._exists(
            f'/repos/{owner}/{repo}/git/trees/{ref}', ref and src) & repo_exists

        if ref_exists:
            raise NotFoundException(
                f'No GitHub file "{src}" found for "{owner}/{repo}:{ref}"')

        elif repo_exists:
            raise NotFoundException(
                f'No GitHub reference "{ref}" found for "{owner}/{repo}"')

        elif owner_exists:
            raise NotFoundException(
                f'No GitHub repository "{repo}" found for "{owner}"')

        else:
            raise NotFoundException(
                f'No GitHub user or organization "{owner}" found"')

    def _list_refs(self, owner, repo, tags=False, branches=False):
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
        refs = list()
        add_ref = refs.append

        releases, status = self._github_api(f'/repos/{owner}/{repo}/releases')
        if status == 404:
            self._raise_not_found(owner, repo)

        for release in releases:
            add_ref(dict(
                ref=release['tag_name'], type='release', desc=release['name']))

        if tags:
            for tag in self._github_api(f'/repos/{owner}/{repo}/tags')[0]:
                add_ref(dict(type='tag', ref=tag['name']))

        if branches:
            for branch in self._github_api(
                    f'/repos/{owner}/{repo}/branches')[0]:
                add_ref(dict(type='branch', ref=branch['name']))

        return refs

    def _list_repos(self, owner):
        """
        List repositories for the specified owner.

        Args:
            owner (str): Repository owner.

        Returns:
            list of str: Repositories names.
        """
        resp, status = self._github_api(f'/orgs/{owner}/repos')
        if status != 404:
            return [repo['name'] for repo in resp['result']]

        resp, status = self._github_api(f'/users/{owner}/repos')
        if status != 404:
            return [repo['name'] for repo in resp['result']]

        self._raise_not_found(owner)

    def get_src_list(self, res_name, res_id):
        """
        Get sources from a specific resource.

        Args:
            res_name (str): Resource name.
            res_id (int): Task ID.

        Returns:
            generator of nun._src.SrcBase subclass: Sources.
        """
        owner, repo, ref, src = self._parse_res_name(res_name)

        # Get reference information
        ref_info = self._get_reference(owner, repo, ref)
        ref = ref_info.get('ref', ref)

        # Archives
        if src in ('zipball', 'tarball'):
            if src == 'zipball':
                file_type = ext = 'zip'
            else:
                ext = 'tar.gz'
                file_type = 'tar'
            yield get_src(
                f'{owner}-{repo}-{ref}.{ext}',
                f'{GITHUB}/{owner}/{repo}/{src}/{ref}', res_name, res_id,
                src_type=file_type, strip_components=1,
                revision=ref_info['revision'])
            return

        # Release assets
        if ref_info.get('assets'):
            yield_assets = False
            for asset in ref_info['assets']:
                if fnmatch(asset['name'], src):
                    yield get_src(
                        asset['name'], asset['browser_download_url'],
                        res_name, res_id, mtime=asset['updated_at'],
                        revision=asset['updated_at'])
                    yield_assets = True
            if yield_assets:
                return

        # Raw file
        # TODO: Get Git tree and apply fnmatch on it
        #       /repos/:owner/:repo/git/trees/:tree_sha
        #       /repos/:owner/:repo/git/trees/:tree_sha?recursive=1
        yield get_src(
            src, f'{GITHUB_RAW}/{owner}/{repo}/{ref}/{src}', res_name,
            res_id, revision=ref_info['revision'])

    def _get_reference(self, owner, repo, ref):
        """
        Reference.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name
            ref (str): Reference name.

        Returns:
            dict or None: dict of reference information if reference found.
        """
        for method in (self._get_release, self._get_branch, self._get_tag,
                       self._get_commit):
            result = method(owner, repo, ref)
            if result:
                return result
        self._raise_not_found(owner, repo, ref)

    def _get_branch(self, owner, repo, ref):
        """
        Get reference as a branch.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name
            ref (str): Reference name.

        Returns:
            dict or None: dict of reference information if reference found.
        """
        if not ref:
            resp, status = self._github_api(f'/repos/{owner}/{repo}')
            if status == 404:
                return None
            ref = resp['default_branch']

        resp, status = self._github_api(f'/repos/{owner}/{repo}/branches/{ref}')
        if status != 404:
            return dict(revision=resp['commit']['sha'], ref=ref,
                        mtime=resp['commit']['commit']['committer']['date'])

    def _get_commit(self, owner, repo, ref):
        """
        Get reference as a commit.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name
            ref (str): Reference name.

        Returns:
            dict or None: dict of reference information if reference found.
        """
        resp, status = self._github_api(f'/repos/{owner}/{repo}/commits/{ref}')
        if status != 404:
            return dict(revision=resp['sha'],
                        mtime=resp['commit']['committer']['date'])

    def _get_release(self, owner, repo, ref):
        """
        Get reference as a release.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name
            ref (str): Reference name.

        Returns:
            dict or None: dict of reference information if reference found.
        """
        if ref:
            url = f'/repos/{owner}/{repo}/releases/tags/{ref}'
        else:
            # Get latest stable release if no reference specified
            url = f'/repos/{owner}/{repo}/releases/latest'

        resp, status = self._github_api(url)
        if status != 404:
            return dict(ref=resp['tag_name'], assets=resp['assets'],
                        revision=resp['created_at'])

    def _get_tag(self, owner, repo, ref):
        """
        Get reference as a tag.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name
            ref (str): Reference name.

        Returns:
            dict or None: dict of reference information if reference found.
        """
        if not ref:
            self._raise_not_found(owner, repo)

        resp, status = self._github_api(f'/repos/{owner}/{repo}/git/tags/{ref}')
        if status != 404:
            return dict(revision=resp['object']['sha'],
                        mtime=resp['tagger']['date'])
