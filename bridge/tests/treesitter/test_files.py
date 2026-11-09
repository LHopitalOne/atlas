import os
import subprocess
import tempfile
import unittest

from atlas_bridge.adapters.treesitter.kit import RepositoryFiles


class RepositoryFilesTest(unittest.TestCase):
    def test_a_git_repository_lists_tracked_and_new_files_not_ignored_ones(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in {'tracked.py': 'a = 1\n', 'new.py': 'b = 2\n', 'out/ignored.py': 'c = 3\n'}.items():
                os.makedirs(os.path.join(d, os.path.dirname(name)), exist_ok=True)
                with open(os.path.join(d, name), 'w') as f:
                    f.write(text)
            with open(os.path.join(d, '.gitignore'), 'w') as f:
                f.write('out/\n')
            git = ['git', '-c', 'user.email=t@t', '-c', 'user.name=t']
            subprocess.run(['git', 'init', '-q'], cwd=d, check=True)
            subprocess.run([*git, 'add', 'tracked.py', '.gitignore'], cwd=d, check=True)
            subprocess.run([*git, 'commit', '-qm', 'x'], cwd=d, check=True)
            self.assertEqual(RepositoryFiles(d).all_paths(), ['.gitignore', 'new.py', 'tracked.py'])


if __name__ == '__main__':
    unittest.main()
