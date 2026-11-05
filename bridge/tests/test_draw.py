import unittest

from atlas_bridge.core.model import CodeGraph, Community
from atlas_bridge.usecases.draw import by_community, by_folder, draw


def graph():
    g = CodeGraph()
    g.file('web', 'src/b.js').community = Community(1, 'ui')
    g.file('web', 'src/a.js').community = Community(1, 'ui')
    g.file('web', 'top.js').community = Community(2, '')
    g.file('api', 'x.py')
    return g


def shape(view):
    return [(r.name, [(d.name, [f.path for f in d.files]) for d in r.domains]) for r in view.repos]


class DrawTest(unittest.TestCase):
    def test_by_community_in_name_order(self):
        self.assertEqual(
            shape(draw(graph())),
            [
                ('api', [('(no community)', ['x.py'])]),
                ('web', [('Community 2', ['top.js']), ('ui', ['src/a.js', 'src/b.js'])]),
            ],
        )

    def test_by_folder(self):
        self.assertEqual(
            shape(draw(graph(), by_folder)),
            [('api', [('(root)', ['x.py'])]), ('web', [('(root)', ['top.js']), ('src', ['src/a.js', 'src/b.js'])])],
        )

    def test_default_grouping_is_community(self):
        self.assertEqual(shape(draw(graph())), shape(draw(graph(), by_community)))


if __name__ == '__main__':
    unittest.main()
