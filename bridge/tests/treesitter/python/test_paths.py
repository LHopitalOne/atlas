import os
import tempfile
import unittest

from atlas_bridge.adapters.treesitter.kit import RepositoryFiles
from atlas_bridge.adapters.treesitter.python import PythonExtractor
from atlas_bridge.adapters.treesitter.python.files import SlashedFiles


class BackslashPathTest(unittest.TestCase):
    """Paths from a directory walk on Windows use '\\': files, modules and imports read them as '/'."""

    FILES = {
        'pkg\\consts.py': "BASE = '/svc'\n",
        'pkg\\m.py': "import requests\nfrom pkg.consts import BASE\nrequests.get(BASE + '/a')\n",
    }

    def test_backslash_paths_are_slashed_and_imports_resolve(self):
        with tempfile.TemporaryDirectory() as d:
            for path, src in self.FILES.items():  # one file per name here: the backslash is part of the name
                with open(os.path.join(d, path), 'w', encoding='utf-8') as f:
                    f.write(src)
            ex = PythonExtractor().extract('r', RepositoryFiles(d), sorted(self.FILES))
        self.assertEqual([(c.file, str(c.path)) for c in ex.calls], [('pkg/m.py', '/svc/a')])

    def test_slashed_files_read_through_the_listed_path(self):
        class Files(RepositoryFiles):
            def read(self, path):
                return path.encode()

        slashed = SlashedFiles(Files('root'), ['a\\b.py', 'c.py'])
        self.assertEqual(slashed.listed(), ['a/b.py', 'c.py'])
        self.assertEqual(slashed.read('a/b.py'), b'a\\b.py')
        self.assertEqual(slashed.read('c.py'), b'c.py')
        self.assertEqual(slashed.root, 'root')
