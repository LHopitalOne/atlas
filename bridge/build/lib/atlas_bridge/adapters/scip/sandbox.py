"""Indexing inside a Docker container: the repository's libraries are installed there (installs may run package
code), so that calls into them resolve in the index, and nothing installed touches this machine."""

import os
import subprocess

from ...core.errors import IndexerFailedError
from .dependencies import PythonDependencies
from .indexers import PythonScipIndexer


class DockerImage:
    """An image built once from a Dockerfile held in code, and reused while its tag (which carries the tool
    versions) is unchanged."""

    def __init__(self, tag: str, dockerfile: str):
        self.tag = tag
        self._dockerfile = dockerfile

    def ensure(self):
        if self._run(['docker', 'image', 'inspect', self.tag]).returncode == 0:
            return
        built = self._run(['docker', 'build', '-t', self.tag, '-'], self._dockerfile)
        if built.returncode != 0:
            raise IndexerFailedError('docker', f'the sandbox image {self.tag}', built.stderr.strip()[-300:])

    @staticmethod
    def _run(cmd, stdin=None):
        return subprocess.run(cmd, input=stdin, capture_output=True, text=True)


class SandboxedPythonIndexer(PythonScipIndexer):
    """scip-python in a throwaway container: the repository is mounted read-only, its declared libraries are
    installed in the container (all at once, else one by one: a `name @ url` that fails is tried by name, and what
    still fails is skipped), then the index is written to the output folder, the only folder the container can
    write."""

    TOOL = 'docker'
    INSTALL = 'install Docker Desktop (or another Docker engine) and start it'
    PYTHON = '3.12'
    HEAP_MB = 3072  # Node's heap inside the container; Docker Desktop's VM has 4 GB by default
    IMAGE = DockerImage(
        f'atlas-scip-python:{PythonScipIndexer.PACKAGE.rsplit("@", 1)[1]}-py{PYTHON}',
        f"""FROM python:{PYTHON}-slim
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs npm && rm -rf /var/lib/apt/lists/*
RUN npm install -g {PythonScipIndexer.PACKAGE}
""",
    )
    SCRIPT = """set -u
install() { python -m pip install --disable-pip-version-check --no-input --quiet --root-user-action=ignore "$@"; }
if [ -s /work/requirements.txt ]; then
  install -r /work/requirements.txt >/dev/null 2>&1 || while IFS= read -r req; do
    name="${req%% @ *}"  # 'sdk @ git+https://...': the same package from the index when the URL fails
    install "$req" >/dev/null 2>&1 || { [ "$name" != "$req" ] && install "$name" >/dev/null 2>&1; } \\
      || echo "atlas: not installed: $req" >&2
  done < /work/requirements.txt
fi
exec scip-python index --project-name "$1" --output "/out/$2" --quiet
"""

    def prepare(self):
        self.IMAGE.ensure()

    def command(self, name, root, out, scratch):
        with open(os.path.join(scratch, 'requirements.txt'), 'w', encoding='utf-8') as f:
            f.writelines(f'{r}\n' for r in PythonDependencies(root).requirements())
        with open(os.path.join(scratch, 'index.sh'), 'w', encoding='utf-8') as f:
            f.write(self.SCRIPT)
        mounts = [(os.path.abspath(root), '/src', 'ro'), (scratch, '/work', 'ro'), (os.path.dirname(out), '/out', 'rw')]
        return [
            'docker', 'run', '--rm',
            *(arg for host, inside, mode in mounts for arg in ('-v', f'{host}:{inside}:{mode}')),
            '-w', '/src',
            '-e', f'NODE_OPTIONS=--max-old-space-size={self.HEAP_MB}',
            self.IMAGE.tag,
            'sh', '/work/index.sh', name, os.path.basename(out),
        ]  # fmt: skip
