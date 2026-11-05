"""Building the ClientRegistry of a repository from its files."""

import re

from .finders import ClientClassFinder, ClientFactoryFinder
from .registry import ClientRegistry


class ClientIndex:
    """Reads the client classes of each file while the file is read for requests (the files that mention a base
    key), then, once every file is read, the factories and variables of the files that construct one of those
    classes (each read anew and dropped at once)."""

    CONSTRUCTED = re.compile(rb'\bnew\s+([A-Za-z_$][\w$]*)\s*\(')  # the class names a file constructs

    def __init__(self, workspace):
        self._workspace = workspace
        self._registry = ClientRegistry()

    def read(self, module):
        """The client classes of a file, read with the module its requests were read with."""
        if module.source.mentions(*ClientRegistry.BASE_BYTES):
            ClientClassFinder(module).add_to(self._registry, module.source.test)

    def build(self) -> ClientRegistry:
        """The registry, with the factories and variables of the classes read so far."""
        classes = self._registry.class_names()
        if classes:
            self._add_factories(classes)
        return self._registry

    def _add_factories(self, classes):
        names = {n.encode() for n in classes}
        for source in self._workspace.sources:
            if names & set(self.CONSTRUCTED.findall(source.data)):
                module = self._workspace.module(source)
                ClientFactoryFinder(module, classes).add_to(self._registry, source.test)
                module.release()
