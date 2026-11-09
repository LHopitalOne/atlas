"""FileMentions: the ChannelMentions port answered by reading a repository's source and configuration files."""

import re

from ....core.errors import SourceReadError
from ....usecases.ports import ChannelMentions
from .files import RepositoryFiles, TestPathPolicy


class FileMentions(ChannelMentions):
    """Where a repository names a channel: a quoted string that is exactly the name, or a config value (`key: name`,
    `key = name`) that is. Test and tooling files are left out; each file is read once, on first use."""

    EXTENSIONS = frozenset(
        {'.py', '.rs', '.js', '.ts', '.tsx', '.mjs', '.yaml', '.yml', '.json', '.toml', '.ini', '.cfg'}
    )
    AROUND = 2  # lines on each side kept as the text around a mention
    QUOTES = '"\'`'
    CONFIG_VALUE = re.compile(r'[:=]\s*(\S+?)\s*(?:#.*)?$')  # `key: value`, `key = value`, a trailing comment

    def __init__(self, roots: dict[str, str]):
        self._roots = roots  # repository name -> folder
        self._texts = {}  # repository name -> [(path, [lines])]
        self._policy = TestPathPolicy()

    def mentions(self, repo, name):
        out = []
        for path, lines in self._files(repo):
            for i, line in enumerate(lines):
                if name in line and self._names(line, name):
                    around = '\n'.join(lines[max(0, i - self.AROUND) : i + self.AROUND + 1])
                    out.append((path, i + 1, around))
        return out

    @classmethod
    def _names(cls, line, name):
        """The line holds `name` as a whole quoted string, or as the value of a config key."""
        if any(f'{q}{name}{q}' in line for q in cls.QUOTES):
            return True
        value = cls.CONFIG_VALUE.search(line)
        return value is not None and value.group(1).strip(cls.QUOTES) == name

    def _files(self, repo):
        if repo not in self._texts:
            root = self._roots.get(repo)
            files = RepositoryFiles(root) if root else None
            paths = [p for p in (files.all_paths() if files else []) if self._wanted(p)]
            self._texts[repo] = [(p, lines) for p in paths if (lines := self._lines(files, p)) is not None]
        return self._texts[repo]

    def _wanted(self, path):
        return path[path.rfind('.') :] in self.EXTENSIONS and not self._policy.is_test(path)

    @staticmethod
    def _lines(files, path):
        try:
            return files.read(path).decode('utf-8', 'replace').splitlines()
        except SourceReadError:
            return None  # unreadable or oversized: nothing to name a channel in
