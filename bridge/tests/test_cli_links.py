import contextlib
import io
import os
import tempfile
import unittest

from atlas_bridge.__main__ import main, split_repo

from .helpers import FIXTURES, load

SHOP = os.path.join(FIXTURES, 'shop')


def run_links(*extra):
    with tempfile.TemporaryDirectory() as d:
        out, graph = os.path.join(d, 'links.json'), os.path.join(d, 'graph.json')
        args = ['links', f'api={SHOP}/api', f'web={SHOP}/web', '-o', out, '--graphify-out', graph, *extra]
        with contextlib.redirect_stderr(io.StringIO()):
            main(args)
        return load(out), load(graph)


class LinksCliTest(unittest.TestCase):
    def test_shop(self):
        found, graph = run_links()
        links = {
            (lk['caller'], lk['target'], lk['call']['method'], lk['call']['path'], lk['status'])
            for lk in found['links']
        }
        self.assertEqual(
            links,
            {
                ('web', 'api', 'POST', '/orders', 'matched'),
                ('web', 'api', 'GET', '/orders/{id}', 'matched'),
                ('web', 'api', 'GET', '/users/{id}', 'unmatched'),
            },
        )
        routes = {lk['route']['path'] for lk in found['links'] if lk['route']}
        self.assertEqual(routes, {'/orders', '/orders/{order_id}'})
        self.assertEqual(found['repos']['api']['routes'], 2)
        self.assertEqual(sum(e['relation'] == 'calls_http' for e in graph['links']), 2)

    def test_split_repo(self):
        self.assertEqual(split_repo('core=/x/y'), ('core', '/x/y'))
        self.assertEqual(split_repo('/x/shop/'), ('shop', '/x/shop/'))


if __name__ == '__main__':
    unittest.main()
