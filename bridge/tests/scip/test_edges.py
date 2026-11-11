"""SCIP uses as code-graph edges (usecases/scipedges.py) read from SCIP indexes (adapters/scip/references.py), and
how they reach the spec (the fourth item of an edge) through folding and the map's index reuse."""

import os
import subprocess
import tempfile
import unittest

from atlas_bridge.adapters.atlas import AtlasSpecPresenter
from atlas_bridge.adapters.graphify import GraphifyLinkWriter
from atlas_bridge.adapters.scip import ScipIndex, ScipReferences
from atlas_bridge.cli.budget import MapBudget
from atlas_bridge.cli.scipcheck import ScipCheck
from atlas_bridge.core.model import CodeGraph, Kind, Ref, Status, Symbol
from atlas_bridge.usecases.draw import MapDrawer
from atlas_bridge.usecases.scipedges import ScipEdges

from .builder import ScipBuilder

SAVE = 'scip-python python shop 0 `shop.store`/Store#save().'
STORE = 'scip-python python shop 0 `shop.store`/Store#'
CHECKOUT = 'scip-python python shop 0 `shop.cart`/checkout().'
LOG = 'scip-python python stdlib 3.12 logging/info().'  # a library: no node on the map
IMPORTED = 'scip-python python shop 0 `shop.store`/'


def index():
    b = ScipBuilder()
    b.occurrence('shop/store.py', 3, STORE, definition=True, span=(3, 20))
    b.occurrence('shop/store.py', 5, SAVE, definition=True, span=(5, 9))
    b.occurrence('shop/cart.py', 10, CHECKOUT, definition=True, span=(10, 30))
    b.occurrence('shop/cart.py', 12, SAVE)  # checkout() calls Store.save()
    b.occurrence('shop/cart.py', 13, LOG)
    b.occurrence('shop/cart.py', 40, STORE)  # module level: the file uses Store
    return ScipIndex(b.build(), 'shop.scip')


def graph():
    g = CodeGraph()
    store, cart = g.file('shop', 'shop/store.py'), g.file('shop', 'shop/cart.py')
    store.symbols += [Symbol('store', 'Store', Kind.CLASS, 3), Symbol('save', '.save()', Kind.FUNCTION, 6)]
    cart.symbols += [Symbol('checkout', 'checkout()', Kind.FUNCTION, 10), Symbol('total', 'total()', Kind.FUNCTION, 32)]
    g.link(Ref('shop', 'shop/cart.py', 'checkout'), Ref('shop', 'shop/store.py', 'save'), Status.INFERRED)
    g.link(Ref('shop', 'shop/cart.py', 'total'), Ref('shop', 'shop/store.py', 'store'), Status.AMBIGUOUS)
    return g


CHECKOUT_REF = Ref('shop', 'shop/cart.py', 'checkout')
SAVE_REF = Ref('shop', 'shop/store.py', 'save')
STORE_REF = Ref('shop', 'shop/store.py', 'store')
CART_FILE = Ref('shop', 'shop/cart.py')


class ScipEdgesTest(unittest.TestCase):
    def setUp(self):
        self.edges = ScipEdges(ScipReferences({'shop': [index()]}))
        self.graph = self.edges.add(graph())

    def test_a_guessed_edge_the_index_shows_is_checked_and_matched(self):
        self.assertIn((CHECKOUT_REF, SAVE_REF), self.graph.checked)
        self.assertEqual(self.graph.links[(CHECKOUT_REF, SAVE_REF)], Status.MATCHED)

    def test_uses_the_graph_lacks_are_added_and_libraries_add_nothing(self):
        self.assertEqual(self.graph.links[(CART_FILE, STORE_REF)], Status.MATCHED)  # a module-level use
        self.assertEqual(len(self.graph.links), 3)  # logging.info has no node on the map
        self.assertIn('SCIP', self.graph.tools)

    def test_the_report_counts_checked_added_and_unseen_guesses(self):
        r = self.edges.report
        self.assertEqual((r.files, r.uses, r.checked, r.added, r.unseen_guesses), (2, 2, 1, 1, 1))
        self.assertEqual(self.graph.links[(Ref('shop', 'shop/cart.py', 'total'), STORE_REF)], Status.AMBIGUOUS)

    def test_names_as_graphify_writes_them(self):
        self.assertEqual(
            [ScipEdges.plain(n) for n in ('save()', '.save()', 'Store', 'a.b.c()')], ['save'] * 2 + ['Store', 'c']
        )

    def test_imports_and_definitions_are_not_uses(self):
        b = ScipBuilder()
        b.occurrence('shop/cart.py', 1, IMPORTED)
        uses = ScipReferences({'shop': [ScipIndex(b.build(), 'x')]}).uses('shop', 'shop/cart.py')
        self.assertEqual([u.key for u in uses], [IMPORTED])  # a module: named, kept; the graph has no node

    def test_a_name_defined_in_several_crates_reaches_none_of_them_unless_exact(self):
        result = 'rust-analyzer cargo {} 0.1 errors/Result#'
        b = ScipBuilder()
        b.occurrence('a/lib.rs', 1, result.format('crate-a'), definition=True)
        b.occurrence('b/lib.rs', 1, result.format('crate-b'), definition=True)
        refs = ScipReferences({'r': [ScipIndex(b.build(), 'x')]})
        self.assertEqual(refs.definition(result.format('crate-b')).file, 'b/lib.rs')  # the exact symbol
        self.assertIsNone(refs.definition(result.format('crate-c')))  # another crate's Result: none
        self.assertEqual(refs.definition(result.format('crate-a').replace('0.1', '0.2')).file, 'a/lib.rs')  # same crate
        self.assertEqual(ScipReferences({'r': [index()]}).definition(SAVE.replace(' 0 ', ' 9 ')).file, 'shop/store.py')


class ScipEdgesOnTheMapTest(unittest.TestCase):
    def test_checked_edges_carry_a_fourth_item_and_survive_folding(self):
        g = ScipEdges(ScipReferences({'shop': [index()]})).add(graph())
        spec = AtlasSpecPresenter().present(MapDrawer().draw(g))
        self.assertEqual(sorted(len(e) for e in spec['edges']), [3, 4, 4])
        MapBudget(max_nodes=1).fit(g)  # every symbol folds into its file
        self.assertEqual(g.checked, {(CART_FILE, Ref('shop', 'shop/store.py'))})


class ScipEdgesInGraphJsonTest(unittest.TestCase):
    def test_seen_edges_are_marked_and_missing_ones_added(self):
        graph = {'nodes': [], 'links': [{'source': 'a', 'target': 'b', 'relation': 'calls', 'confidence': 'INFERRED'}]}
        GraphifyLinkWriter.add_checked(graph, [('a', 'b'), ('a', 'c')])
        self.assertEqual(
            [(e['target'], e['relation'], e['confidence'], e['scip']) for e in graph['links']],
            [('b', 'calls', 'EXTRACTED', True), ('c', 'uses', 'EXTRACTED', True)],
        )


class ScipIndexReuseTest(unittest.TestCase):
    def test_an_index_is_reused_while_the_commit_and_changes_are_the_same(self):
        with tempfile.TemporaryDirectory() as d:
            git = ['git', '-C', d, '-c', 'user.name=t', '-c', 'user.email=t@t']
            subprocess.run(['git', 'init', '-q', d], check=True)
            subprocess.run([*git, 'commit', '-q', '--allow-empty', '-m', 'start'], check=True)
            check, log = ScipCheck(d, lambda line: None), []
            state = check._state(d)
            out = os.path.join(d, 'scip', 'x.python.scip')
            os.makedirs(os.path.dirname(out))
            open(out, 'wb').close()
            check._stamp(out, state)
            self.assertEqual(check._stamped(out), state)
            self.assertEqual(check._state(d), state)  # the index written inside the repository is no change
            with open(os.path.join(d, 'new.py'), 'w') as f:
                f.write('x = 1\n')
            self.assertNotEqual(check._state(d), state)  # an uncommitted change means a new index
            self.assertEqual(ScipCheck(d, log.append)._state('/'), '')  # outside git: never reused


if __name__ == '__main__':
    unittest.main()
