"""What a parameter holds: its default, and the arguments the calls of its function pass for it, in this file and in
the files that import it (a constructor through `new Class(...)`, a method through `this.method(...)` or an imported
instance, a function by name)."""

from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax


class Callers:
    """Finds the calls of the function a parameter belongs to. Only plain parameters are followed (not destructured
    ones), and only up to MAX_SITES calls."""

    MAX_SITES = 50
    CONSTRUCTOR = 'constructor'
    CALLS = frozenset({'call_expression', 'new_expression'})

    def __init__(self, file):
        self._file = file

    def arguments(self, param):
        """[(file, expression)] the parameter may hold: what each call passes, or its default where a call leaves it
        out (or when no call is found)."""
        fn, index = self._function(param)
        default = self._default(param)
        if fn is None:
            return []
        found, omitted = [], False
        for file, call in self._sites(fn)[: self.MAX_SITES]:
            args = JsSyntax.args(call)
            if index < len(args):
                found.append((file, args[index]))
            else:
                omitted = True
        if default is not None and (omitted or not found):
            found.append((self._file, default))
        return found

    @staticmethod
    def _function(param):
        """(the function the parameter belongs to, its position); (None, -1) for anything but a plain parameter."""
        formal = param.parent
        if formal is None or formal.type != 'formal_parameters' or formal.parent is None:
            return None, -1
        params = [p for p in formal.named_children if p.type != 'comment']
        return formal.parent, next(i for i, p in enumerate(params) if p.id == param.id)

    @staticmethod
    def _default(param):
        if param.type == 'assignment_pattern':
            return param.child_by_field_name('right')
        return param.child_by_field_name('value') if param.type in JsSyntax.PARAMETERS else None

    def _sites(self, fn):
        name = Functions.name(fn)
        if not name:
            return []
        _, owner = Functions.enclosing(fn)
        if fn.type == 'method_definition' and name == self.CONSTRUCTOR:
            return self._calls(owner, lambda file, call: self._is_new(file, call, owner))
        if fn.type == 'method_definition':
            return self._calls(name, lambda file, call: self._is_method_call(file, call, name, owner))
        return self._calls(name, lambda file, call: self._is_call(file, call, name))

    def _calls(self, name, fits):
        files = [self._file, *self._file.graph.importers(self._file.path, name)]
        return [(f, c) for f in files for c in JsSyntax.walk(f.module.source.root, self.CALLS) if fits(f, c)]

    def _is_new(self, file, call, owner):
        ctor = call.child_by_field_name('constructor') if call.type == 'new_expression' else None
        return ctor is not None and ctor.type == 'identifier' and self._names_this(file, ctor, owner)

    def _is_call(self, file, call, name):
        fn = JsSyntax.unwrap(call.child_by_field_name('function')) if call.type == 'call_expression' else None
        return fn is not None and fn.type == 'identifier' and self._names_this(file, fn, name)

    def _is_method_call(self, file, call, name, owner):
        """`this.name(...)` in the class, or `x.name(...)` on an instance this file imports or makes."""
        fn = JsSyntax.unwrap(call.child_by_field_name('function')) if call.type == 'call_expression' else None
        if fn is None or fn.type != 'member_expression' or JsSyntax.text(fn.child_by_field_name('property')) != name:
            return False
        obj = JsSyntax.unwrap(fn.child_by_field_name('object'))
        if obj.type == 'this':
            return file is self._file and Functions.enclosing(call)[1] == owner
        if obj.type != 'identifier':
            return False
        if file is not self._file:
            found = file.imported(obj)
            return found is not None and found[0] is self._file
        made = JsSyntax.unwrap(file.module.scopes.lookup(obj, JsSyntax.text(obj)))
        return made is not None and made.type == 'new_expression' and self._is_new(file, made, owner)

    def _names_this(self, file, ident, name):
        """`ident` is `name` of this file: in this file by name, elsewhere imported from this file (by that name, or
        as its default export)."""
        if file is self._file:
            return JsSyntax.text(ident) == name
        found = file.libraries.source_of(ident)
        if found is None or found[1] not in (name, file.libraries.DEFAULT):
            return False
        return file.graph.file_for(file.path, found[0]) is self._file
