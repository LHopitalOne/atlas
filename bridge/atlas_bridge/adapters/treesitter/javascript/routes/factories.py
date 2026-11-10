"""Routers made by functions: an Express router factory (`adminRouter(bank)` returns the `router` it declares routes
on) and a Fastify plugin (`async (app) => { app.get(...) }`, registered with a prefix)."""

from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..syntax.params import Params


class RouterFunctions:
    """The receiver name the routes of a function of a file are declared on."""

    @classmethod
    def receiver(cls, module, name) -> str | None:
        """The router a top-level function `name` of the module stands for: the name it returns (a factory), else
        its first parameter (a plugin the framework hands an instance to); None when `name` is no such function."""
        fn = cls._function(module, name)
        if fn is None:
            return None
        returned = cls._returned_name(fn)
        if returned:
            return returned
        params = Params.of(fn)
        return params[0].name if params and params[0].name else None

    @classmethod
    def _function(cls, module, name):
        for child in module.source.root.named_children:
            if child.type == 'export_statement':
                child = child.child_by_field_name('declaration') or child
            if child.type in Functions.FUNCTIONS and JsSyntax.text(child.child_by_field_name('name')) == name:
                return child
            if child.type in JsSyntax.DECLARATIONS:
                found = cls._declared(child, name)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _declared(declaration, name):
        """The function a `const name = ...` of the declaration binds, or None."""
        for d in declaration.named_children:
            value = JsSyntax.unwrap(d.child_by_field_name('value')) if d.type == 'variable_declarator' else None
            named = value is not None and JsSyntax.text(d.child_by_field_name('name')) == name
            if named and value.type in Functions.FUNCTIONS:
                return value
        return None

    @staticmethod
    def _returned_name(fn):
        """The identifier a function returns: an arrow's expression body, or a `return name;` of its own body."""
        body = fn.child_by_field_name('body')
        if body is None:
            return ''
        if body.type != 'statement_block':
            body = JsSyntax.unwrap(body)
            return JsSyntax.text(body) if body.type == 'identifier' else ''
        for ret in JsSyntax.walk(body, {'return_statement'}):
            if JsSyntax.ancestor(ret, Functions.FUNCTIONS) != fn:
                continue
            value = JsSyntax.unwrap(ret.named_children[0]) if ret.named_children else None
            if value is not None and value.type == 'identifier':
                return JsSyntax.text(value)
        return ''
