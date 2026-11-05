"""Use case: arrange a code graph as a map of repositories > domains > files, ready for a presenter."""

import posixpath
from dataclasses import dataclass

from ..core.model import CodeGraph, SourceFile


def by_community(f: SourceFile):
    """Group files by the community a graph tool detected for them."""
    if f.community is None:
        return '(no community)'
    return f.community.name or f'Community {f.community.id}'


def by_folder(f: SourceFile):
    return posixpath.dirname(f.path) or '(root)'


GROUPINGS = {'community': by_community, 'folder': by_folder}


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


def draw(graph: CodeGraph, grouping=by_community) -> MapView:
    """Repos, domains and files in name order, so the same graph always gives the same map."""
    tree = {}
    for f in graph.files.values():
        tree.setdefault(f.repo, {}).setdefault(grouping(f), []).append(f)
    repos = [
        Repo(repo, [Domain(d, sorted(fs, key=lambda f: f.path)) for d, fs in sorted(doms.items())])
        for repo, doms in sorted(tree.items())
    ]
    return MapView(repos, graph)
