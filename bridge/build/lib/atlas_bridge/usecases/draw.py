"""Use case: arrange a code graph as a map of repositories > domains > files, ready for a presenter."""

import posixpath
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core.model import CodeGraph, SourceFile


class Grouping(ABC):
    """Decides which domain (territory on the map) a file belongs to."""

    name = ''

    @abstractmethod
    def domain(self, f: SourceFile) -> str: ...


class CommunityGrouping(Grouping):
    """Files grouped by the community a graph tool detected for them."""

    name = 'community'

    def domain(self, f):
        if f.community is None:
            return '(no community)'
        return f.community.name or f'Community {f.community.id}'


class FolderGrouping(Grouping):
    name = 'folder'

    def domain(self, f):
        return posixpath.dirname(f.path) or '(root)'


GROUPINGS = {g.name: g for g in (CommunityGrouping(), FolderGrouping())}


@dataclass(frozen=True)
class Domain:
    name: str
    files: list[SourceFile]


@dataclass(frozen=True)
class Repo:
    name: str
    domains: list[Domain]


@dataclass(frozen=True)
class MapView:
    repos: list[Repo]
    graph: CodeGraph


class MapDrawer:
    """Repos, domains and files in name order, so the same graph always gives the same map."""

    def __init__(self, grouping: Grouping = GROUPINGS['community']):
        self._grouping = grouping

    def draw(self, graph: CodeGraph) -> MapView:
        tree = {}
        for f in graph.files.values():
            tree.setdefault(f.repo, {}).setdefault(self._grouping.domain(f), []).append(f)
        repos = [
            Repo(repo, [Domain(d, sorted(fs, key=lambda f: f.path)) for d, fs in sorted(doms.items())])
            for repo, doms in sorted(tree.items())
        ]
        return MapView(repos, graph)
