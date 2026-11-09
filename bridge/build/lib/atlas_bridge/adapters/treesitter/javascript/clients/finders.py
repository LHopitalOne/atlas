"""Finding what one file says about clients: its client classes, and the functions and variables that make one."""

from abc import ABC, abstractmethod

from ...kit import UrlTemplate
from ..syntax.functions import Functions
from ..syntax.members import Members
from ..syntax.nodes import JsSyntax
from ..values.urls import UrlText
from .registry import ClientRegistry


class ClientFinder(ABC):
    """Reads one file (a JsModule) and records what it finds in a ClientRegistry."""

    def __init__(self, module):
        self._module = module

    @abstractmethod
    def add_to(self, registry: ClientRegistry, test: bool):
        """Record what the file says; `test` marks it as test code, which loses to code outside tests."""


class ClientClassFinder(ClientFinder):
    """Classes that keep a base URL in a field: `this.baseUrl = options.baseUrl ?? '/api/0'`."""

    def add_to(self, registry, test):
        registry.add_classes(self.find(), test)

    def find(self):
        """{class name: default base path}."""
        out = {}
        for cls in JsSyntax.walk(self._module.source.root, Functions.CLASSES):
            if not cls.is_named:  # the `class` keyword
                continue
            name = JsSyntax.text(cls.child_by_field_name('name'))
            for key in ClientRegistry.BASE_KEYS:
                values = Members.field_values(cls, key)
                if name and values:
                    out[name] = self._default_base(values)
                    break
        return out

    def _default_base(self, values):
        for v in values:
            value = self._module.values.resolve(v, set())
            if JsSyntax.unwrap(v).type == 'string' and not value:
                return ''  # baseUrl = ''
            path = UrlTemplate.split(value).path if UrlText.literal(value) else None
            if path is not None and not path.startswith('/{'):
                return path
        return ClientRegistry.UNKNOWN_BASE


class ClientFactoryFinder(ClientFinder):
    """Functions that return a new client (`useApi()`) and module variables that hold one (`QUERY_API_CLIENT`)."""

    def __init__(self, module, class_names):
        super().__init__(module)
        self._classes = class_names

    def add_to(self, registry, test):
        factories, variables = self.find()
        registry.add_factories(factories, test)
        registry.add_variables(variables, test)

    def find(self):
        """({function: spec}, {module variable: spec}) for clients of the known classes made in the file."""
        factories, variables = {}, {}
        for new in JsSyntax.walk(self._module.source.root, {'new_expression'}):
            if JsSyntax.text(new.child_by_field_name('constructor')) not in self._classes:
                continue
            spec = self._module.clients.made_by(new, set())
            fn = Functions.named_ancestor(new)
            if fn is not None:
                if Functions.returns(fn):
                    factories.setdefault(Functions.name(fn), spec)
                continue
            name = self._declared_name(new)
            if name is not None:
                variables.setdefault(name, spec)
        return factories, variables

    @staticmethod
    def _declared_name(new):
        """The variable `new Client()` is the initializer of, or None."""
        parent = JsSyntax.outer_parent(new)
        if parent is not None and parent.type == 'variable_declarator':
            return JsSyntax.text(parent.child_by_field_name('name'))
        return None
