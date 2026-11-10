"""Where a name or member chain is given its value: through const bindings, destructuring, object literals and
imports from other files of the repository."""

from dataclasses import dataclass

from ..syntax.nodes import JsSyntax


@dataclass(frozen=True)
class Location:
    """An expression and the file (a JsModule) it is written in; resolve it with that module's values."""

    module: object
    node: object


class ObjectPaths:
    """Follows an expression of one file to the expression its value is written as.

    `config.orders.baseUrl` -> the `baseUrl` property of the object literal `config` is bound to;
    `const { baseUrl, endpoints } = config.orders` binds each name to the property of that object; an imported
    name is followed to what the other file exports (`export const config = {...} as const`) when the module linker
    can read that file. `Object.freeze({...})` is its object.
    """

    MAX_DEPTH = 8  # bindings, properties and imports followed
    NAMES = frozenset({'identifier', 'shorthand_property_identifier'})
    FREEZE = 'Object.freeze'

    def __init__(self, module, linker=None):
        self._module = module
        self._linker = linker

    def locate(self, node, depth=0) -> Location | None:
        """Where the value of `node` is written: the expression itself when it is not a name or member chain."""
        node = self._unwrap(node)
        if node is None or depth > self.MAX_DEPTH:
            return None
        if node.type in self.NAMES:
            return self._name(node, depth)
        if node.type == 'member_expression':
            key = node.child_by_field_name('property')
            if key is None or key.type != 'property_identifier':
                return None
            return self._member(node.child_by_field_name('object'), JsSyntax.text(key), depth)
        if node.type == 'subscript_expression':
            key = JsSyntax.unwrap(node.child_by_field_name('index'))
            if key is None or key.type != 'string':
                return None
            return self._member(node.child_by_field_name('object'), JsSyntax.string(key), depth)
        required = JsSyntax.require(node)
        if required:
            return self._exported(required, self._module.imports.DEFAULT, depth)
        return Location(self._module, node)

    def origin(self, node, depth=0) -> Location | None:
        """Where the value a name holds is written, following names only (bindings, then imports of the repository)
        and stopping at the first expression that is not a name: `export const router = t.router` -> `t.router`,
        which locate() would try to read as a property of an object literal. None for a parameter."""
        node = self._unwrap(node)
        if node is None or depth > self.MAX_DEPTH:
            return None
        if node.type not in self.NAMES:
            return Location(self._module, node)
        name = JsSyntax.text(node)
        binding = self._module.scopes.binding(node, name)
        if binding is not None:
            return self.origin(binding.initializer, depth + 1) if binding.initializer is not None else None
        imported = self._module.imports.get(name)
        target = self._linker.module(self._module.path, imported[0]) if imported and self._linker else None
        value = target.exports.value(imported[1]) if target is not None else None
        return target.objects.origin(value, depth + 1) if value is not None else None

    def property(self, location: Location, key, depth=0) -> Location | None:
        """Where property `key` of the object literal at `location` is written."""
        obj = self._unwrap(location.node)
        if obj is None or obj.type != 'object':
            return None
        value = JsSyntax.prop(obj, key)
        return location.module.objects.locate(value, depth + 1) if value is not None else None

    def _unwrap(self, node):
        node = JsSyntax.unwrap(node)
        if node is not None and node.type == 'call_expression':
            args = JsSyntax.args(node)
            if JsSyntax.text(node.child_by_field_name('function')) == self.FREEZE and args:
                return JsSyntax.unwrap(args[0])
        return node

    def _member(self, obj, key, depth):
        base = self.locate(obj, depth + 1)
        return self.property(base, key, depth + 1) if base is not None else None

    def _name(self, node, depth):
        name = JsSyntax.text(node)
        binding = self._module.scopes.binding(node, name)
        if binding is None:
            return self._imported(name, depth)
        if binding.initializer is not None:
            return self.locate(binding.initializer, depth + 1)
        declarator = binding.node
        if declarator.type != 'variable_declarator' or declarator.child_by_field_name('value') is None:
            return None  # a parameter: its value is the caller's
        keys = self._keys(declarator.child_by_field_name('name'), name)
        found = self.locate(declarator.child_by_field_name('value'), depth + 1) if keys else None
        for key in keys or ():
            found = self.property(found, key, depth + 1) if found is not None else None
        return found

    def _imported(self, name, depth):
        imported = self._module.imports.get(name)
        return self._exported(imported[0], imported[1], depth) if imported is not None else None

    def _exported(self, source, name, depth):
        """Where the value a file of the repository exports as `name` is written."""
        target = self._linker.module(self._module.path, source) if self._linker is not None else None
        value = target.exports.value(name) if target is not None else None
        return target.objects.locate(value, depth + 1) if value is not None else None

    @classmethod
    def _keys(cls, pattern, name):
        """The property keys from a destructuring pattern down to `name`: `{ a: { b: name } }` -> ['a', 'b']."""
        if pattern is None or pattern.type != 'object_pattern':
            return None
        for p in pattern.named_children:
            if p.type == 'shorthand_property_identifier_pattern' and JsSyntax.text(p) == name:
                return [name]
            if p.type == 'object_assignment_pattern' and JsSyntax.text(p.child_by_field_name('left')) == name:
                return [name]
            if p.type == 'pair_pattern':
                found = cls._pair_keys(p, name)
                if found is not None:
                    return found
        return None

    @classmethod
    def _pair_keys(cls, pair, name):
        key, value = pair.child_by_field_name('key'), pair.child_by_field_name('value')
        key = JsSyntax.string(key) if key.type == 'string' else JsSyntax.text(key)
        if value.type == 'assignment_pattern':
            value = value.child_by_field_name('left')
        if value.type == 'identifier':
            return [key] if JsSyntax.text(value) == name else None
        inner = cls._keys(value, name)
        return [key, *inner] if inner is not None else None
