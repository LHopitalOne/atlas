import unittest

from atlas_bridge.core.model import CodeGraph, Ref, Status


class ModelTest(unittest.TestCase):
    def test_certainty_order(self):
        order = sorted(Status, key=lambda s: s.certainty)
        self.assertEqual(order, [Status.MATCHED, Status.INFERRED, Status.AMBIGUOUS, Status.UNMATCHED])

    def test_repeated_link_keeps_most_certain(self):
        g, a, b = CodeGraph(), Ref('r', 'a.py'), Ref('r', 'b.py')
        g.link(a, b, Status.AMBIGUOUS)
        g.link(a, b, Status.MATCHED)
        g.link(a, b, Status.INFERRED)
        self.assertEqual(g.links, {(a, b): Status.MATCHED})

    def test_self_link_dropped(self):
        g, a = CodeGraph(), Ref('r', 'a.py')
        g.link(a, a, Status.MATCHED)
        self.assertEqual(g.links, {})

    def test_file_is_created_once(self):
        g = CodeGraph()
        self.assertIs(g.file('r', 'a.py'), g.file('r', 'a.py'))
        self.assertEqual(g.file('r', 'a.py').ref, Ref('r', 'a.py'))


if __name__ == '__main__':
    unittest.main()
