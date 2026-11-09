"""ClientSpec: how a request's client is made, and how its base path is found from that."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ClientSpec(ABC):
    """How a request's client is made. Each kind finds its own base path in the ClientRegistry."""

    name: str

    def base(self, registry, depth=0):
        """The base path requests of this client go under, or None when the repository does not say. Specs that lead
        to other specs stop after registry.MAX_DEPTH steps."""
        return None if depth >= registry.MAX_DEPTH else self._base(registry, depth)

    @abstractmethod
    def _base(self, registry, depth): ...


@dataclass(frozen=True)
class KnownBase(ClientSpec):
    """A client made with its base path given (`axios.create({baseURL: '/api'})`): name is that path."""

    def base(self, registry, depth=0):
        return self.name

    def _base(self, registry, depth):
        return self.name


@dataclass(frozen=True)
class ClientClass(ClientSpec):
    """An instance of a class (`new Client()`, a parameter typed `Client`): the class's default base path."""

    @classmethod
    def typed(cls, type_name):
        """The client of a parameter or member annotated with a type, or None without one."""
        return cls(type_name) if type_name else None

    def _base(self, registry, depth):
        return registry.class_base(self.name)


@dataclass(frozen=True)
class MadeClient(ClientSpec):
    """A client named by something the repository defines once: followed to the spec it is made with."""

    def _base(self, registry, depth):
        found = self._made(registry).get(self.name)
        if found is None or len(found) != 1:
            return None
        return next(iter(found)).base(registry, depth + 1)

    @abstractmethod
    def _made(self, registry):
        """The table of the registry this kind of client is looked up in."""


@dataclass(frozen=True)
class ClientFactory(MadeClient):
    """Returned by a function of the repository (`useApi()`)."""

    def _made(self, registry):
        return registry.factories


@dataclass(frozen=True)
class ClientVariable(MadeClient):
    """Held by a module variable of the repository (`QUERY_API_CLIENT`), possibly imported."""

    def _made(self, registry):
        return registry.variables
