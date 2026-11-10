"""Where a repository lives and a few lines of its code, so the page can show and link every line it cites.

Code is read from the repository folders at build time and embedded in the spec: the page is static and cannot
fetch it. Each line shown also links to GitHub at the commit the folder is checked out at.
"""

import os
import re
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class RepoOrigin:
    """A repository's web address and the commit its folder is at; empty when git cannot tell."""

    url: str = ''
    commit: str = ''

    SSH_REMOTE = re.compile(r'^git@([^:]+):(.+?)(?:\.git)?/?$')  # git@github.com:owner/name.git
    HTTP_REMOTE = re.compile(r'^(https?://[^\s]+?)(?:\.git)?/?$')  # https://github.com/owner/name(.git)

    @classmethod
    def of(cls, folder: str) -> 'RepoOrigin':
        return cls(cls.web_url(cls._git(folder, 'remote', 'get-url', 'origin')), cls._git(folder, 'rev-parse', 'HEAD'))

    @classmethod
    def web_url(cls, remote: str) -> str:
        ssh = cls.SSH_REMOTE.match(remote)
        if ssh:
            return f'https://{ssh.group(1)}/{ssh.group(2)}'
        web = cls.HTTP_REMOTE.match(remote)
        return web.group(1) if web else ''

    @staticmethod
    def _git(folder, *args):
        try:
            out = subprocess.run(['git', '-C', folder, *args], capture_output=True, text=True, check=False, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return ''
        return out.stdout.strip() if out.returncode == 0 else ''


class CodeSource:
    """Lines of code from repository folders given as {repo: folder}; repositories with no folder give nothing.
    `origins` fixes a repository's address and commit instead of asking git (for tests and copied folders)."""

    BEFORE = 2  # lines shown above the cited line
    AFTER = 4  # ...and below it
    MAX_WIDTH = 160  # longer lines are cut, so one minified line cannot bloat the page

    def __init__(self, folders: dict[str, str] | None = None, origins: dict[str, RepoOrigin] | None = None):
        self._folders = dict(folders or {})
        self._files: dict[tuple[str, str], list[str]] = {}
        self._origins: dict[str, RepoOrigin] = dict(origins or {})

    def origin(self, repo: str) -> RepoOrigin:
        if repo not in self._origins:
            folder = self._folders.get(repo)
            self._origins[repo] = RepoOrigin.of(folder) if folder else RepoOrigin()
        return self._origins[repo]

    def snippet(self, repo: str, path: str, line: int) -> tuple[int, list[str]]:
        """(first line number, lines) around `line`; (0, []) when the file cannot be read."""
        lines = self._lines(repo, path)
        if not lines or line < 1:
            return 0, []
        start = max(1, line - self.BEFORE)
        shown = lines[start - 1 : min(len(lines), line + self.AFTER)]
        while len(shown) > self.BEFORE + 1 and not shown[-1].strip():
            shown.pop()
        return start, [s[: self.MAX_WIDTH] for s in shown]

    def _lines(self, repo, path):
        key = (repo, path)
        if key not in self._files:
            self._files[key] = self._read(self._folders.get(repo), path)
        return self._files[key]

    @staticmethod
    def _read(folder, path):
        if not folder:
            return []
        full = os.path.normpath(os.path.join(folder, path))
        if not full.startswith(os.path.normpath(folder) + os.sep):
            return []  # a path that leaves the repository folder
        try:
            with open(full, encoding='utf-8', errors='replace') as f:
                return f.read().splitlines()
        except OSError:
            return []
