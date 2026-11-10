"""What every Rust call collector shares: the workspace's files and one value resolver."""

from abc import abstractmethod

from .....core.http import Extraction
from ...kit import CallCollector
from ..guard import StackGuard


class RustCallCollector(CallCollector):
    """Runs calls(file, node) on every node of one capture, each guarded against exhausting the stack."""

    CAPTURE = ''  # the RustFile capture whose nodes may send requests

    def __init__(self, workspace, values):
        super().__init__(workspace)
        self._values = values

    def collect(self) -> Extraction:
        out = Extraction()
        for f in self.workspace.files:
            for node in f.nodes(self.CAPTURE):
                out.calls += StackGuard.run(self.calls, f, node)
        return out

    @abstractmethod
    def calls(self, file, node) -> list:
        """The calls one node makes."""
