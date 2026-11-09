"""The requests a generated client file sends through its runtime: `oazapfts.fetchJson(`/pets/${id}`, opts)`."""

from dataclasses import replace

from .....core.http import ANY
from ...kit import UrlTemplate
from ..calls.forwarding import OpenRequest
from ..calls.pending import PendingRequest
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..values.urls import UrlText
from .runtime import GeneratedRuntimes, NamespaceImports


class RuntimeInstances:
    """The runtimes a file makes (`const oazapfts = Oazapfts.runtime(defaults)`, or `runtime(defaults)` imported by
    name), each with the base URL of its defaults: name -> (GeneratedRuntime, base)."""

    def __init__(self, module, spaces: NamespaceImports):
        self._module = module
        self._spaces = spaces
        self.found = {}
        for declarator in JsSyntax.walk(module.source.root, {'variable_declarator'}):
            name = declarator.child_by_field_name('name')
            value = JsSyntax.unwrap(declarator.child_by_field_name('value'))
            runtime = self._runtime(value) if value is not None and value.type == 'call_expression' else None
            if runtime is not None and name is not None and name.type == 'identifier':
                self.found[JsSyntax.text(name)] = (runtime, self._base(runtime, JsSyntax.args(value)))

    def _runtime(self, call):
        """The runtime library whose factory a call makes a runtime with, or None."""
        fn = JsSyntax.unwrap(call.child_by_field_name('function'))
        if fn.type == 'member_expression':
            space = JsSyntax.unwrap(fn.child_by_field_name('object'))
            library = self._spaces.get(JsSyntax.text(space)) if space.type == 'identifier' else None
            runtime = GeneratedRuntimes.of(library)
            factory = JsSyntax.text(fn.child_by_field_name('property'))
        else:
            imported = self._module.imports.get(JsSyntax.text(fn)) if fn.type == 'identifier' else None
            runtime = GeneratedRuntimes.of(imported[0]) if imported is not None else None
            factory = imported[1] if imported is not None else ''
        return runtime if runtime is not None and factory == runtime.factory else None

    def _base(self, runtime, args):
        """The base URL the defaults give ('' when they give none; None when it is not known)."""
        found = self._module.objects.locate(args[0]) if args else None
        given = self._module.objects.property(found, runtime.base) if found is not None else None
        if given is None:
            return ''
        value = given.module.values.resolve(given.node, set())
        return value.rstrip('/') if value is not None and not UrlText.PLACEHOLDER.search(value) else None


class GeneratedRequests:
    """Reads the requests of one file: (closed requests, requests still open on their function's parameters). The
    URL is read as a template whose query-string helpers are left out, behind the runtime's base URL; the method is
    the `method` of the options (inside a wrapper such as `oazapfts.json({...})`), GET when they name none."""

    DEFAULT_METHOD = 'GET'

    def __init__(self, workspace, module):
        self._workspace = workspace
        self._module = module
        self._spaces = NamespaceImports(module.source)
        self._runtimes = RuntimeInstances(module, self._spaces).found

    @classmethod
    def read(cls, workspace, module):
        if not module.source.mentions(*GeneratedRuntimes.MENTIONS):
            return [], []
        return cls(workspace, module)._requests()

    def _requests(self):
        closed, opened = [], []
        if not self._runtimes:
            return closed, opened
        for call in JsSyntax.walk(self._module.source.root, {'call_expression'}):
            sender = self._sender(call)
            args = JsSyntax.args(call)
            if sender is None or not args or sender[1] is None:
                continue
            hints = set()
            url = self._url(args[0], hints)
            if url is None:
                continue
            value, method = sender[1] + url, self._method(sender[0], args[1] if len(args) > 1 else None)
            found = OpenRequest.at(call, value, method, '', hints)
            if found is not None:
                opened.append(replace(found, path=self._module.path))
            elif UrlText.matchable(value) and UrlText.path_like(value):
                closed += self._pending(call, value, method, hints)
        return closed, opened

    def _sender(self, call):
        """(runtime, base) when a call sends a request through a runtime of the file, else None."""
        fn = JsSyntax.unwrap(call.child_by_field_name('function'))
        if fn is None or fn.type != 'member_expression':
            return None
        found = self._runtimes.get(JsSyntax.text(JsSyntax.unwrap(fn.child_by_field_name('object'))))
        sends = found is not None and JsSyntax.text(fn.child_by_field_name('property')) in found[0].senders
        return found if sends else None

    def _url(self, node, hints):
        """The URL template, without a trailing query string a query helper builds."""
        node = JsSyntax.unwrap(node)
        if node.type != 'template_string':
            return self._module.values.resolve(node, hints)
        out = ''
        for c in node.children:
            if c.type in ('string_fragment', 'escape_sequence'):
                out += JsSyntax.text(c)
            elif c.type == 'template_substitution' and c.named_children:
                if self._is_query(c.named_children[0]):
                    break  # the query string: the rest of the URL is not path
                out = UrlText.join(out, self._module.values.resolve(c.named_children[0], hints), c.named_children[0])
        return out

    def _is_query(self, node):
        node = JsSyntax.unwrap(node)
        if node is None or node.type != 'call_expression':
            return False
        head = JsSyntax.callee_head(node.child_by_field_name('function'))
        imported = self._module.imports.get(head)
        library = self._spaces.get(head) or (imported[0] if imported is not None else None)
        return GeneratedRuntimes.is_query(library)

    def _method(self, runtime, options):
        options = self._unwrapped(runtime, options) if options is not None else None
        if options is None:
            return self.DEFAULT_METHOD
        if options.type != 'object':
            return ANY  # options made elsewhere: the method is not known
        method = JsSyntax.prop(options, 'method')
        if method is None:
            return self.DEFAULT_METHOD
        method = JsSyntax.unwrap(method)
        return (JsSyntax.string(method) or ANY).upper() if method.type == 'string' else ANY

    @staticmethod
    def _unwrapped(runtime, options):
        """The options object inside a runtime wrapper (`oazapfts.json({...})`), or the options as given."""
        options = JsSyntax.unwrap(options)
        if options.type != 'call_expression':
            return options
        fn = JsSyntax.unwrap(options.child_by_field_name('function'))
        args = JsSyntax.args(options)
        wraps = fn.type == 'member_expression' and JsSyntax.text(fn.child_by_field_name('property')) in runtime.wrappers
        return JsSyntax.unwrap(args[0]) if wraps and args else options

    def _pending(self, call, value, method, hints):
        url = UrlTemplate.split(UrlText.with_params(value))
        if url.path is None:
            return []
        function, owner = Functions.enclosing(call)
        hints.update(url.hints)
        hints.update(h for h in (function, owner, self._module.path) if h)
        test = self._workspace.is_test(self._module.source, call)
        line = JsSyntax.line(call)
        return [PendingRequest(self._module.source, line, method, function, frozenset(hints), test, url.path, None)]
