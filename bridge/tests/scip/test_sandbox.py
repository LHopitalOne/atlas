import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

from atlas_bridge.adapters.scip import (
    INDEXERS,
    DockerImage,
    PythonDependencies,
    PythonScipIndexer,
    SandboxedPythonIndexer,
)
from atlas_bridge.cli.index import IndexCommand
from atlas_bridge.core.errors import IndexerFailedError


def write(root, files):
    for path, text in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(text))


class PythonDependenciesTest(unittest.TestCase):
    def requirements(self, files):
        with tempfile.TemporaryDirectory() as d:
            write(d, files)
            return PythonDependencies(d).requirements()

    def test_requirements_files(self):
        found = self.requirements(
            {
                'requirements.txt': """
                # the server
                Flask>2.3  # web
                -r requirements/base.txt
                -e .
                ./vendored/lib
                --index-url https://example.org/simple
                sdk @ git+https://github.com/org/sdk.git
                """,
                'requirements/base.txt': 'requests~=2.31\n',
                'requirements/test.txt': 'pytest\n',
                'requirements-dev.txt': 'black\n',
                'notes.md': 'not requirements\n',
            }
        )
        self.assertEqual(found, ['Flask>2.3', 'requests~=2.31', 'sdk @ git+https://github.com/org/sdk.git'])

    @unittest.skipIf(sys.version_info < (3, 11), 'tomllib is Python 3.11+')
    def test_pyproject_lists(self):
        found = self.requirements(
            {
                'pyproject.toml': """
                [project]
                dependencies = ["django (>=4.2)", "boto3"]

                [tool.poetry.dependencies]
                python = "^3.10"
                httpx = "^0.27"
                torch = { version = "^2", optional = true }
                pydantic = { version = ">=2" }
                """,
            }
        )
        self.assertEqual(found, ['django (>=4.2)', 'boto3', 'httpx', 'pydantic'])

    def test_nothing_declared(self):
        self.assertEqual(self.requirements({'pyproject.toml': 'not = [toml'}), [])
        self.assertEqual(self.requirements({'setup.py': 'setup()\n'}), [])


class SandboxTest(unittest.TestCase):
    def test_the_container_reads_the_repository_and_writes_only_the_index(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as scratch:
            write(root, {'requirements.txt': 'requests\n'})
            out = os.path.join(scratch, 'out', 'svc.python.scip')
            cmd = SandboxedPythonIndexer().command('svc', root, out, scratch)
            mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == '-v']
            self.assertEqual(
                mounts,
                [f'{os.path.abspath(root)}:/src:ro', f'{scratch}:/work:ro', f'{os.path.dirname(out)}:/out:rw'],
            )
            self.assertEqual(cmd[-4:], ['sh', '/work/index.sh', 'svc', 'svc.python.scip'])
            with open(os.path.join(scratch, 'requirements.txt')) as f:
                self.assertEqual(f.read(), 'requests\n')
            script = os.path.join(scratch, 'index.sh')
            self.assertEqual(subprocess.run(['sh', '-n', script]).returncode, 0)  # valid shell
        self.assertIn('pip install --disable-pip-version-check', SandboxedPythonIndexer.SCRIPT)  # options after install

    def test_the_image_is_built_once(self):
        image = DockerImage('atlas-test:1', 'FROM scratch\n')
        done = subprocess.CompletedProcess([], 0, '', '')
        with mock.patch('subprocess.run', return_value=done) as run:
            image.ensure()
        self.assertEqual(run.call_count, 1)  # inspect found it
        missing, failed = (
            subprocess.CompletedProcess([], 1, '', 'no such image'),
            subprocess.CompletedProcess([], 1, '', 'boom'),
        )
        with mock.patch('subprocess.run', side_effect=[missing, done]) as run:
            image.ensure()
        self.assertEqual(run.call_args.kwargs['input'], 'FROM scratch\n')
        with mock.patch('subprocess.run', side_effect=[missing, failed]), self.assertRaises(IndexerFailedError):
            image.ensure()

    def test_sandbox_option_swaps_only_the_python_indexer(self):
        swapped = IndexCommand._indexers(True)
        self.assertIn(SandboxedPythonIndexer, swapped)
        self.assertNotIn(PythonScipIndexer, swapped)
        self.assertEqual(len(swapped), len(INDEXERS))
        self.assertIs(IndexCommand._indexers(False), INDEXERS)


if __name__ == '__main__':
    unittest.main()
