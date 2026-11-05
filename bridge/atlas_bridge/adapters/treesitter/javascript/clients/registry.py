"""The repository's HTTP clients: classes and their default base path, factories and variables that make one."""

from .specs import ClientSpec


class ClientTable:
    """{name: {value}} read from the files of a repository. Code outside tests wins over test code: a name defined
    outside tests forgets its test definitions, and test definitions never join it."""

    def __init__(self):
        self._values = {}
        self._test = {}

    def add(self, found, test):
        """Record {name: value} of one file."""
        for name, value in found.items():
            if name not in self._values or (self._test[name] and not test):
                self._values[name], self._test[name] = {value}, test
            elif self._test[name] == test:
                self._values[name].add(value)

    def get(self, name):
        """The values of `name`, or None when no file defines it."""
        return self._values.get(name)

    def names(self):
        return frozenset(self._values)


class ClientRegistry:
    """What the repository says about its HTTP clients, by name: classes and their default base path, functions that
    make a client, module variables that hold one."""

    BASE_KEYS = ('baseUrl', 'baseURL', 'prefixUrl', 'prefixURL', 'basePath')  # where a client keeps its base
    BASE_BYTES = tuple(k.encode() for k in BASE_KEYS)
    UNKNOWN_BASE = '/{base}'  # a repository client whose base path cannot be read
    MAX_DEPTH = 5  # factories and variables followed to a class

    def __init__(self):
        self._classes = ClientTable()  # class name -> {default base path}
        self._factories = ClientTable()  # function name -> {ClientSpec}
        self._variables = ClientTable()  # module variable -> {ClientSpec}

    @property
    def factories(self) -> ClientTable:
        return self._factories

    @property
    def variables(self) -> ClientTable:
        return self._variables

    def add_classes(self, found, test):
        """{class name: default base path} of one file."""
        self._classes.add(found, test)

    def add_factories(self, found, test):
        """{function name: ClientSpec} of one file."""
        self._factories.add(found, test)

    def add_variables(self, found, test):
        """{module variable: ClientSpec} of one file."""
        self._variables.add(found, test)

    def class_names(self):
        return self._classes.names()

    def class_base(self, name):
        """The default base path of a client class; UNKNOWN_BASE when its files disagree; None for another class."""
        found = self._classes.get(name)
        if found is None:
            return None  # not a client class of this repository
        return next(iter(found)) if len(found) == 1 else self.UNKNOWN_BASE

    def base(self, spec: ClientSpec):
        """The base path requests of this client go under, or None when the repository does not say."""
        return spec.base(self)

    def prefixed(self, path, spec: ClientSpec):
        """`path` under the base path of its client."""
        base = self.base(spec)
        if base and base != '/' and path != base and not path.startswith(base.rstrip('/') + '/'):
            return base.rstrip('/') + '/' + path.lstrip('/')
        return path
