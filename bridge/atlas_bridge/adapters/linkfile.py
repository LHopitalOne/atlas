"""Adapter out: links as plain JSON, for scoring against an answer key (eval/score.py) and for other tools."""

from ..core.http import Extraction


def route_json(r):
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


def present(links, extraction: Extraction, repos):
    counts = {
        repo: {
            'routes': sum(r.repo == repo for r in extraction.routes),
            'calls': sum(c.repo == repo and not c.test for c in extraction.calls),
            'test_calls': sum(c.repo == repo and c.test for c in extraction.calls),
        }
        for repo in repos
    }
    return {
        'repos': counts,
        'links': [
            {
                'caller': link.source,
                'target': link.target,
                'status': link.status.name.lower(),
                'reason': link.reason,
                'call': {
                    'file': link.call.file,
                    'line': link.call.line,
                    'function': link.call.function,
                    'method': link.call.method,
                    'path': str(link.call.path) if link.call.path else None,
                    'kind': link.call.kind,
                    'route_name': link.call.route_name,
                    'test': link.call.test,
                },
                'route': route_json(link.route) if link.route else None,
            }
            for link in links
        ],
    }
