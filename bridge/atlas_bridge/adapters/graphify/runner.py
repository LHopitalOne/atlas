"""Adapter: the Graphify command line, run on a repository to write its graphify-out/graph.json (no LLM needed)."""

import os
import shutil
import subprocess
import sys
import tempfile
import time

from ...core.errors import GraphifyFailedError, GraphifyUnavailableError


class GraphifyRunner:
    """Finds the graphify command installed next to this Python (pipx, a venv) or on PATH, and runs
    `graphify update .` in a repository, so the graph's source_file paths are relative to the repository root.
    A large repository takes Graphify minutes; `progress(seconds)` is called every HEARTBEAT seconds meanwhile."""

    OUT = os.path.join('graphify-out', 'graph.json')
    TAIL = 400  # characters of graphify's output kept in an error message
    HEARTBEAT = 30  # seconds between progress calls

    def __init__(self, progress=None):
        self._progress = progress or (lambda seconds: None)

    def graph_path(self, root: str) -> str:
        return os.path.join(root, self.OUT)

    def has_graph(self, root: str) -> bool:
        return os.path.isfile(self.graph_path(root))

    def update(self, name: str, root: str) -> str:
        """Build or refresh the repository's graph; returns graph.json's path."""
        with tempfile.TemporaryFile('w+', encoding='utf-8', errors='replace') as log:
            code = self._run(name, root, log)
            log.seek(0)
            output = log.read().strip()
        if code != 0 or not self.has_graph(root):
            raise GraphifyFailedError(name, output[-self.TAIL :] or 'no graph.json written')
        return self.graph_path(root)

    def _run(self, name, root, log):
        """Run graphify with its output in `log`; returns its exit code."""
        env = {**os.environ, 'GRAPHIFY_NO_AUTO_REFRESH': '1', 'GRAPHIFY_NO_TIPS': '1'}
        try:
            proc = subprocess.Popen([self.executable(), 'update', '.'], cwd=root, env=env, stdout=log, stderr=log)
        except OSError as e:
            raise GraphifyFailedError(name, e.strerror or str(e)) from e
        start = time.monotonic()
        while True:
            try:
                return proc.wait(timeout=self.HEARTBEAT)
            except subprocess.TimeoutExpired:
                self._progress(time.monotonic() - start)
            except BaseException:  # Ctrl-C: do not leave graphify running
                proc.kill()
                raise

    @staticmethod
    def executable() -> str:
        name = 'graphify.exe' if os.name == 'nt' else 'graphify'
        beside = os.path.join(os.path.dirname(sys.executable), name)
        if os.path.isfile(beside):
            return beside
        found = shutil.which('graphify')
        if found is None:
            raise GraphifyUnavailableError()
        return found
