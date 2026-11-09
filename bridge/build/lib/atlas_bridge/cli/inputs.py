"""Command-line inputs as small value objects that check themselves and raise InputError subclasses."""

import json
import os
from dataclasses import dataclass

from ..core.errors import AliasError, GraphFormatError, NamedInputError, RepositoryNotFoundError


@dataclass(frozen=True)
class NamedInput:
    """'name=path', or a plain path whose name is derived from it."""

    name: str
    path: str

    @classmethod
    def parse(cls, item: str):
        name, sep, path = item.partition('=')
        if sep and (not name or not path):
            raise NamedInputError(item)
        return cls(name, path) if sep else cls(cls.default_name(item), item)

    @staticmethod
    def default_name(path):
        return os.path.basename(os.path.abspath(path))


class GraphInput(NamedInput):
    """A Graphify graph.json, named after the folder that holds graphify-out/, or the file's stem."""

    @staticmethod
    def default_name(path):
        path = os.path.abspath(path)
        parent = os.path.dirname(path)
        if os.path.basename(parent) == 'graphify-out':
            return os.path.basename(os.path.dirname(parent))
        return os.path.splitext(os.path.basename(path))[0]

    def load(self):
        return JsonFile.read(self.path)


class ScipInput(NamedInput):
    """A SCIP index for one repository: 'name=index.scip', or a file named '<repo>[.<language>].scip'."""

    SUFFIX = '.scip'

    @staticmethod
    def default_name(path):
        return os.path.basename(path).split('.')[0]

    @classmethod
    def in_folder(cls, folder):
        """Every index in a folder, named after its file."""
        try:
            names = sorted(os.listdir(folder))
        except OSError as e:
            raise RepositoryNotFoundError(folder) from e
        return [cls.parse(os.path.join(folder, n)) for n in names if n.endswith(cls.SUFFIX)]


class RepositoryInput(NamedInput):
    """A repository folder."""

    def checked(self):
        if not os.path.isdir(self.path):
            raise RepositoryNotFoundError(self.path)
        return self


class Aliases:
    """'--alias word=repo' arguments as a dict."""

    @staticmethod
    def parse(items):
        out = {}
        for item in items:
            word, sep, repo = item.partition('=')
            if not sep or not word or not repo:
                raise AliasError(item)
            out[word] = repo
        return out


class JsonFile:
    @staticmethod
    def read(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except OSError as e:
            raise GraphFormatError(path, e.strerror or str(e)) from e
        except json.JSONDecodeError as e:
            raise GraphFormatError(path, f'invalid JSON at line {e.lineno}') from e

    @staticmethod
    def write(path, data, indent=None):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, separators=None if indent else (',', ':'))
