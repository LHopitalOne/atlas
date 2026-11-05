"""Adapter out: links as plain JSON, for scoring against an answer key (eval/score.py) and for other tools."""

from ..usecases.link import LinkReport
from .base import Presenter


class LinkFilePresenter(Presenter):
    def present(self, result: LinkReport):
        return {
            'repos': {repo: self._counts(result.extraction, repo) for repo in result.repos},
            'links': [self._link(link) for link in result.links],
        }

    @staticmethod
    def _counts(extraction, repo):
        return {
            'routes': sum(r.repo == repo for r in extraction.routes),
            'calls': sum(c.repo == repo and not c.test for c in extraction.calls),
            'test_calls': sum(c.repo == repo and c.test for c in extraction.calls),
        }

    def _link(self, link):
        c = link.call
        return {
            'caller': link.source,
            'target': link.target,
            'status': link.status.name.lower(),
            'reason': link.reason,
            'call': {
                'file': c.file,
                'line': c.line,
                'function': c.function,
                'method': c.method,
                'path': str(c.path) if c.path else None,
                'kind': c.kind,
                'route_name': c.route_name,
                'test': c.test,
            },
            'route': self.route(link.route) if link.route else None,
        }

    @staticmethod
    def route(r):
        return {
            'repo': r.repo,
            'file': r.file,
            'line': r.line,
            'methods': sorted(r.methods),
            'path': str(r.path),
            'handler': r.handler,
            'name': r.name,
            'framework': r.framework,
        }
