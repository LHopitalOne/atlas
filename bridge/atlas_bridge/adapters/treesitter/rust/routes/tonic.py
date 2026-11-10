"""gRPC services served with tonic: `impl <Service> for <Type>` of the trait tonic generates in `<service>_server`."""

import dataclasses

from .....core.http import Extraction, Protocol
from ...kit import RouteCollector
from ..names import ItemPath
from ..syntax import RustSyntax


class TonicServices(RouteCollector):
    """tonic-build turns `service Indexer { rpc IndexNote(..) }` into a trait `Indexer` in a module `indexer_server`,
    with one method per rpc in snake_case (`index_note`). Each fn of an `impl` of such a trait, outside test code, is
    a route '/<Service>/<Method>' (the method in the proto's CamelCase; like a Python servicer, without the proto
    package). The trait is known by its path, as written or as the file's `use` declarations expand it."""

    MENTION = b'tonic'
    SUFFIX = '_server'  # the module tonic generates a service's server side in
    METHOD = 'CALL'  # the operation of every gRPC route and call
    framework = 'tonic'

    def collect(self) -> Extraction:
        out = Extraction()
        for f in self.workspace.files:
            if not f.mentions(self.MENTION):
                continue
            for impl in f.nodes('impl'):
                service = self.service(f, impl)
                if service and not self.workspace.is_test(f, impl):
                    out.routes += self._methods(f, impl, service)
        return out

    @classmethod
    def service(cls, file, impl) -> str:
        """The service an impl serves ('Indexer'), or '' when it does not implement a tonic service trait."""
        trait = impl.child_by_field_name('trait')
        if trait is None:
            return ''
        segments = ItemPath.imported(file, trait)
        if len(segments) < 2 or not segments[-2].endswith(cls.SUFFIX):
            return ''
        module, name = segments[-2].removesuffix(cls.SUFFIX), segments[-1]
        return name if module.replace('_', '') == name.lower() else ''

    def _methods(self, file, impl, service):
        body = impl.child_by_field_name('body')
        owner = ItemPath.last(impl.child_by_field_name('type'))
        out = []
        for fn in body.named_children if body is not None else ():
            if fn.type != 'function_item':
                continue
            name = RustSyntax.name(fn)
            path = f'/{service}/{self.camel(name)}'
            route = self.route(file, file.line(fn), path, {self.METHOD}, f'{owner}::{name}')
            out.append(dataclasses.replace(route, protocol=Protocol.GRPC))
        return out

    @staticmethod
    def camel(name):
        """'index_note' -> 'IndexNote': the rpc name tonic made the method name from."""
        return ''.join(part[:1].upper() + part[1:] for part in name.split('_'))
