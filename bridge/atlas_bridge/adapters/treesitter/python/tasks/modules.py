"""The dotted name Python gives a module, from its file path: what Celery names a task after by default."""

import posixpath


class ModuleNames:
    """'apps/api/proj/tasks/mail.py' is 'proj.tasks.mail' when 'apps/api/proj' is the first folder on the way that is
    a package (it holds an `__init__.py`): the folders above it are where the interpreter is started, not part of the
    name. A file with no package above it is named by its whole path from the repository root."""

    INIT = '__init__'
    SUFFIX = '.py'

    def __init__(self, paths):
        self._packages = {posixpath.dirname(p) for p in paths if posixpath.basename(p) == self.INIT + self.SUFFIX}

    def of(self, path: str) -> str:
        parts = path.removesuffix(self.SUFFIX).split('/')
        if parts[-1] == self.INIT:
            parts = parts[:-1]
        top = next((i for i in range(len(parts) - 1) if '/'.join(parts[: i + 1]) in self._packages), 0)
        return '.'.join(parts[top:])
