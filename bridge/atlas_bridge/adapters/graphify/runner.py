"""Adapter: the Graphify command line, run on a repository to write its graphify-out/graph.json (no LLM needed)."""

import os
import shutil
import subprocess
import sys

from ...core.errors import GraphifyFailedError, GraphifyUnavailableError


class GraphifyRunner:
    """Finds the graphify command installed next to this Python (pipx, a venv) or on PATH, and runs
    `graphify update .` in a repository, so the graph's source_file paths are relative to the repository root."""

    OUT = os.path.join('graphify-out', 'graph.json')
    TAIL = 400  # characters of graphify's output kept in an error message

    def graph_path(self, root: str) -> str:
        return os.path.join(root, self.OUT)

    def has_graph(self, root: str) -> bool:
        return os.path.isfile(self.graph_path(root))

    def update(self, name: str, root: str) -> str:
        """Build or refresh the repository's graph; returns graph.json's path."""
        done = subprocess.run(
            [self.executable(), 'update', '.'],
            cwd=root,
            env={**os.environ, 'GRAPHIFY_NO_AUTO_REFRESH': '1', 'GRAPHIFY_NO_TIPS': '1'},
            capture_output=True,
            text=True,
            errors='replace',
        )
        if done.returncode != 0 or not self.has_graph(root):
            problem = (done.stderr.strip() or done.stdout.strip())[-self.TAIL :] or 'no graph.json written'
            raise GraphifyFailedError(name, problem)
        return self.graph_path(root)

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
