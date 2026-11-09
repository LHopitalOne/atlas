"""JsModule: one javascript / typescript file as the collectors read it."""

from .bindings.exports import ModuleExports
from .bindings.imports import ImportTable
from .bindings.receivers import Receivers
from .bindings.scopes import Scopes
from .clients.resolver import ClientResolver
from .declarations.table import RouteSyntaxes
from .syntax.site import CallSite
from .values.objects import ObjectPaths
from .values.resolver import UrlValues


class JsModule:
    """A source file with its call sites, scopes, URL values, imports, receivers, clients and route syntaxes. Made
    once per file and pass, and shared by the collectors of that pass, so each scope is read and each binding
    resolved once. Its caches depend on the order bindings are resolved in, so a pass never reuses another's. With
    a linker (linker.ModuleLinker), values are followed into the files it imports."""

    def __init__(self, source, linker=None):
        self._source = source
        self._scopes = Scopes()
        self._imports = ImportTable(source)
        self._exports = ModuleExports(source)
        self._objects = ObjectPaths(self, linker)
        self._values = UrlValues(self._scopes, self._objects)
        self._receivers = Receivers(self._scopes, self._imports)
        self._clients = ClientResolver(source, self._scopes, self._imports, self._values)
        self._route_syntax = None
        self._sites = None

    @property
    def source(self):
        return self._source

    @property
    def path(self):
        return self._source.path

    @property
    def scopes(self) -> Scopes:
        return self._scopes

    @property
    def imports(self) -> ImportTable:
        return self._imports

    @property
    def exports(self) -> ModuleExports:
        return self._exports

    @property
    def objects(self) -> ObjectPaths:
        return self._objects

    @property
    def values(self) -> UrlValues:
        return self._values

    @property
    def receivers(self) -> Receivers:
        return self._receivers

    @property
    def clients(self) -> ClientResolver:
        return self._clients

    @property
    def route_syntax(self) -> RouteSyntaxes:
        """How the file's member calls declare routes and mounts (made on first use)."""
        if self._route_syntax is None:
            self._route_syntax = RouteSyntaxes(self._receivers)
        return self._route_syntax

    def sites(self) -> list[CallSite]:
        """The file's call sites, in source order (found once)."""
        if self._sites is None:
            self._sites = CallSite.all_in(self._source)
        return self._sites

    def release(self):
        """Drop the file's syntax tree and everything read from it; the module must not be used afterwards."""
        self._sites = None
        self._source.release()
