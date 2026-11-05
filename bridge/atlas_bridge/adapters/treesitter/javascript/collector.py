"""Collectors that read a workspace file by file, alone or together in one pass that parses each file once."""

from abc import abstractmethod

from ....core.http import Extraction
from ..kit import Collector


class FileCollector(Collector):
    """Reads each file of a pass (start, then read per file, then finish). A file's syntax tree is dropped once the
    file is read unless a collector keeps it, so memory stays bounded by the files that declare something."""

    def __init__(self, workspace):
        super().__init__(workspace)
        self.start()

    def collect(self) -> Extraction:
        return FilePass(self.workspace, (self,)).run()

    @abstractmethod
    def start(self):
        """Forget what an earlier pass found."""

    @abstractmethod
    def read(self, module):
        """Read one file (a JsModule shared by the collectors of the pass)."""

    def keeps(self, module) -> bool:
        """The collector holds on to the module until it finishes."""
        return False

    @abstractmethod
    def finish(self) -> Extraction:
        """What the files read in this pass declare or send."""


class FilePass:
    """One pass of file collectors over the scanned files of a workspace: every file is read with a new JsModule,
    handed to each collector in order, then released unless a collector keeps it."""

    def __init__(self, workspace, collectors):
        self._workspace = workspace
        self._collectors = tuple(collectors)

    def run(self) -> Extraction:
        kept = []
        for collector in self._collectors:
            collector.start()
        for module in self._workspace.modules():
            for collector in self._collectors:
                collector.read(module)
            if any(c.keeps(module) for c in self._collectors):
                kept.append(module)
            else:
                module.release()
        out = Extraction()
        for collector in self._collectors:
            out.extend(collector.finish())
        for module in kept:
            module.release()
        return out


class SharedPass(Collector):
    """Several file collectors run in one pass, so each file is parsed once for all of them. Their results come out
    in the order the collectors are given."""

    def __init__(self, workspace, collectors):
        super().__init__(workspace)
        self._collectors = tuple(collectors)

    @property
    def collectors(self):
        return self._collectors

    def collect(self) -> Extraction:
        return FilePass(self.workspace, self._collectors).run()
