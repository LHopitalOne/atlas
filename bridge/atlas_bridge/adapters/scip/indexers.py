"""Running SCIP indexers on a repository: each language's indexer, in a mode that never runs the repository's code."""

import json
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod

from ...core.errors import IndexerFailedError, IndexerUnavailableError


class ScipIndexer(ABC):
    """One language's indexer. Subclasses say which repositories it applies to and the command that indexes one."""

    TOOL = ''  # the executable that must be on PATH
    INSTALL = ''  # how to get it
    LANGUAGE = ''  # used in the output file name: <repo>.<language>.scip
    MARKERS: tuple[str, ...] = ()  # files at the repository root that mean this indexer applies

    def applies(self, root: str) -> bool:
        return any(os.path.exists(os.path.join(root, m)) for m in self.MARKERS)

    def index(self, name: str, root: str, out_dir: str) -> str:
        """Index the repository into out_dir; returns the .scip file's path."""
        if shutil.which(self.TOOL) is None:
            raise IndexerUnavailableError(self.TOOL, self.INSTALL)
        self.prepare()
        out = os.path.abspath(os.path.join(out_dir, f'{name}.{self.LANGUAGE}.scip'))
        with tempfile.TemporaryDirectory() as scratch:
            done = subprocess.run(
                self.command(name, root, out, scratch),
                cwd=root,
                env={**os.environ, **self.environment()},
                capture_output=True,
                text=True,
            )
        if done.returncode != 0 or not os.path.exists(out):
            raise IndexerFailedError(self.TOOL, name, (done.stderr or done.stdout).strip()[-300:] or 'no index written')
        return out

    def prepare(self):
        """Anything the command needs first (an image to build); nothing by default."""
        return None

    @abstractmethod
    def command(self, name: str, root: str, out: str, scratch: str) -> list[str]:
        """The command line, run in the repository's root; `scratch` is a folder for temporary files."""

    def environment(self) -> dict:
        return {}


class PythonScipIndexer(ScipIndexer):
    """scip-python: Pyright's analysis, written as SCIP. It reads the code and runs none of it."""

    TOOL, LANGUAGE = 'npx', 'python'
    INSTALL = 'install Node.js (npx runs @sourcegraph/scip-python)'
    MARKERS = ('pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt')
    PACKAGE = '@sourcegraph/scip-python@0.6.8'
    HEAP_MB = 16384  # large repositories (Sentry's 8,500 files) run out of Node's default heap

    def command(self, name, root, out, scratch):
        return ['npx', '-y', self.PACKAGE, 'index', '--project-name', name, '--output', out, '--quiet']

    def environment(self):
        return {'NODE_OPTIONS': f'--max-old-space-size={self.HEAP_MB}'}


class RustScipIndexer(ScipIndexer):
    """rust-analyzer, with build scripts and procedural macros switched off so that no repository code runs. Names
    that only exist in macro output stay unresolved."""

    TOOL, LANGUAGE = 'rust-analyzer', 'rust'
    INSTALL = 'rustup component add rust-analyzer'
    MARKERS = ('Cargo.toml',)
    SAFE = {'cargo': {'buildScripts': {'enable': False}}, 'procMacro': {'enable': False}}

    def command(self, name, root, out, scratch):
        config = os.path.join(scratch, 'rust-analyzer.json')
        with open(config, 'w', encoding='utf-8') as f:
            json.dump(self.SAFE, f)
        return ['rust-analyzer', 'scip', '.', '--output', out, '--config-path', config, '--exclude-vendored-libraries']


class TypeScriptScipIndexer(ScipIndexer):
    """scip-typescript, for TypeScript and (with an inferred tsconfig) JavaScript. It runs none of the code."""

    TOOL, LANGUAGE = 'npx', 'typescript'
    INSTALL = 'install Node.js (npx runs @sourcegraph/scip-typescript)'
    MARKERS = ('tsconfig.json', 'package.json')
    PACKAGE = '@sourcegraph/scip-typescript@0.6.1'

    def command(self, name, root, out, scratch):
        cmd = ['npx', '-y', self.PACKAGE, 'index', '--output', out]
        return cmd if os.path.exists(os.path.join(root, 'tsconfig.json')) else [*cmd, '--infer-tsconfig']


INDEXERS = (PythonScipIndexer, RustScipIndexer, TypeScriptScipIndexer)
