"""GraphqlResolvers: the root fields a JavaScript GraphQL server resolves, read from its resolver map."""

import dataclasses
from typing import NamedTuple

from .....core.http import ANY, Extraction, Protocol
from ...kit import RouteCollector
from ..syntax.nodes import JsSyntax


class SchemaBuilder(NamedTuple):
    """A function or class of a library that builds a schema from `{ typeDefs, resolvers }`, its first argument."""

    library: str
    name: str
    form: str  # the node that calls it: a call_expression or a new_expression


class GraphqlResolvers(RouteCollector):
    """A schema written SDL-first is served by its resolver map: `createSchema({ typeDefs, resolvers })`
    (graphql-yoga), `makeExecutableSchema(...)` (graphql-tools), `new ApolloServer(...)`. Each field of the map's root
    types Query, Mutation and Subscription is a GRAPHQL route '/<field>', placed at the field's key: the name clients
    select. The map, a root type's object and the objects spread into them are followed through bindings and imports
    of the repository; a part that is not an object literal there adds nothing."""

    CALL, NEW = 'call_expression', 'new_expression'
    BUILDERS = (
        SchemaBuilder('graphql-yoga', 'createSchema', CALL),
        SchemaBuilder('@graphql-tools/schema', 'makeExecutableSchema', CALL),
        SchemaBuilder('graphql-tools', 'makeExecutableSchema', CALL),
        SchemaBuilder('@apollo/server', 'ApolloServer', NEW),
        SchemaBuilder('apollo-server', 'ApolloServer', NEW),
        SchemaBuilder('apollo-server-express', 'ApolloServer', NEW),
    )
    MENTIONS = tuple(sorted({f'{q}{b.library}{q}'.encode() for b in BUILDERS for q in '\'"'}))
    RESOLVERS = 'resolvers'
    ROOTS = frozenset({'Query', 'Mutation', 'Subscription'})
    MAX_DEPTH = 4  # arrays and spreads followed inside one resolver map
    MEMBERS = frozenset({'pair', 'method_definition'})
    KEYS = frozenset({'property_identifier', 'string'})  # a computed key (`[name]`) names no field we can read

    def collect(self) -> Extraction:
        out, seen = Extraction(), set()
        linker = self.workspace.linker()
        for source in self.workspace.sources:
            if source.test or not source.mentions(*self.MENTIONS):
                continue
            module = self.workspace.module(source, linker)
            for node in JsSyntax.walk(source.root, {self.CALL, self.NEW}):
                builder = self._builder(module, node)
                for route in self._routes(module, node, builder) if builder is not None else ():
                    if (route.file, route.line, str(route.path)) not in seen:
                        seen.add((route.file, route.line, str(route.path)))
                        out.routes.append(route)
        linker.release()
        return out

    def _builder(self, module, node):
        """The schema builder a call or `new` is, by the name its file imports it as, or None."""
        callee = JsSyntax.unwrap(node.child_by_field_name('function' if node.type == self.CALL else 'constructor'))
        if callee is None or callee.type != 'identifier':
            return None
        imported = module.imports.get(JsSyntax.text(callee))
        return next((b for b in self.BUILDERS if imported == (b.library, b.name) and node.type == b.form), None)

    def _routes(self, module, node, builder):
        args = JsSyntax.args(node)
        options = module.objects.locate(args[0]) if args else None
        given = JsSyntax.prop(options.node, self.RESOLVERS) if options is not None else None
        resolvers = options.module.objects.locate(given) if given is not None else None
        out = []
        for found in self._objects(resolvers, 0):
            for key, value in self._members(found):
                root = JsSyntax.text(key)
                if root in self.ROOTS and value is not None:
                    out += self._fields(found.module.objects.locate(value), root, builder)
        return out

    def _fields(self, location, root, builder):
        out = []
        for found in self._objects(location, 0):
            for key, _ in self._members(found):
                field = JsSyntax.string(key) if key.type == 'string' else JsSyntax.text(key)
                route = self.route(found.module.source, JsSyntax.line(key), '/' + field, {ANY}, f'{root}.{field}')
                out.append(dataclasses.replace(route, protocol=Protocol.GRAPHQL, framework=builder.library))
        return out

    def _objects(self, location, depth):
        """The object literals a resolver map is written as: itself, the maps of an array of them (graphql-tools
        merges them), and the objects spread into it."""
        node = JsSyntax.unwrap(location.node) if location is not None else None
        if node is None or depth > self.MAX_DEPTH:
            return []
        if node.type == 'array':
            items = [location.module.objects.locate(i) for i in node.named_children]
            return [o for i in items for o in self._objects(i, depth + 1)]
        if node.type != 'object':
            return []
        found = [dataclasses.replace(location, node=node)]
        for spread in (c for c in node.named_children if c.type == 'spread_element' and c.named_children):
            found += self._objects(location.module.objects.locate(spread.named_children[0]), depth + 1)
        return found

    def _members(self, location):
        """(key, value or None) of each member of an object literal whose name is written."""
        for member in location.node.named_children:
            if member.type == 'shorthand_property_identifier':
                yield member, member
            elif member.type in self.MEMBERS:
                key = member.child_by_field_name('key' if member.type == 'pair' else 'name')
                if key is not None and key.type in self.KEYS:
                    yield key, member.child_by_field_name('value')
