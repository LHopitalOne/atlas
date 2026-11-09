"""The Python libraries a repository declares, read from its files (nothing is run): requirements files,
pyproject.toml's [project] list and Poetry's table. An indexer installs them so that calls into them resolve."""

import os
import re

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: pyproject.toml is not read, requirements files still are
    tomllib = None


class PythonDependencies:
    """Requirement strings pip understands, from the files at a repository's root and in requirements/.

    Files for tests, development, docs and linting are left out: the index is of the code that ships. Lines that
    point into the repository itself (`-e .`, `./lib`) or change pip's options are skipped; `-r other.txt` is followed
    inside the same folder.
    """

    FOLDER = 'requirements'
    TEXT = re.compile(r'^[\w.-]+\.txt$')  # a requirements file's name
    NOT_SHIPPED = re.compile(r'test|dev|doc|lint|ci\b|mypy|type', re.I)  # files that are not the shipped code's
    INCLUDE = re.compile(r'^-r\s+(?P<path>\S+)|^--requirement[=\s]+(?P<long>\S+)')  # `-r base.txt`
    OPTION = re.compile(r'^-')  # any other pip option: -e, -i, --hash...
    LOCAL = re.compile(r'^(\.|/|file:)')  # a path into the repository
    COMMENT = re.compile(r'\s+#.*$')  # a trailing comment
    MAX_INCLUDES = 8  # -r chains followed per file

    def __init__(self, root: str):
        self._root = root

    def requirements(self) -> list[str]:
        out = [*self._pyproject(), *self._files()]
        return list(dict.fromkeys(out))

    def _files(self):
        names = [n for n in self._listing(self._root) if n.startswith('requirements')]
        names += [os.path.join(self.FOLDER, n) for n in self._listing(os.path.join(self._root, self.FOLDER))]
        lines = []
        for name in names:
            if self.TEXT.match(os.path.basename(name)) and not self.NOT_SHIPPED.search(name):
                lines += self._read(os.path.join(self._root, name), self.MAX_INCLUDES)
        return lines

    @staticmethod
    def _listing(folder):
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def _read(self, path, budget):
        if budget <= 0 or not os.path.isfile(path):
            return []
        out = []
        with open(path, encoding='utf-8', errors='replace') as f:
            for raw in f:
                line = self.COMMENT.sub('', raw.strip())
                include = self.INCLUDE.match(line)
                if include:
                    other = include.group('path') or include.group('long')
                    out += self._read(os.path.join(os.path.dirname(path), other), budget - 1)
                elif line and not line.startswith('#') and not self.OPTION.match(line) and not self.LOCAL.match(line):
                    out.append(line)
        return out

    def _pyproject(self):
        path = os.path.join(self._root, 'pyproject.toml')
        if tomllib is None or not os.path.isfile(path):
            return []
        try:
            with open(path, 'rb') as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            return []
        listed = data.get('project', {}).get('dependencies', [])
        poetry = data.get('tool', {}).get('poetry', {}).get('dependencies', {})
        return [*(r for r in listed if isinstance(r, str)), *self._poetry(poetry)]

    @staticmethod
    def _poetry(table):
        """Poetry's {name: version or {version, optional}}: the names (its ^ and ~ versions are not pip's), leaving
        out python and optional extras."""
        return [
            name
            for name, spec in table.items()
            if name != 'python' and not (isinstance(spec, dict) and spec.get('optional'))
        ]
