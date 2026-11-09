"""Calls to the library entry points of the table, with the argument that is the address."""

from typing import NamedTuple

from ..names import ItemPath
from ..syntax import RustSyntax
from .table import EntryPoint, EntryPoints


class ChannelSite(NamedTuple):
    """One call to an entry point: what it is, the call, and the argument holding the address."""

    entry: EntryPoint
    call: object
    address: object


class ChannelSites:
    """Which calls reach an entry point. A call on a type (`TcpStream::connect`) is recognised by the type's full
    path through the file's `use` declarations; a call on a value (`socket.send_to`) by the type ValueTypes reads
    for the value. A call whose type is not known is not a site."""

    def __init__(self, types, entries=None):
        self._types = types
        self._entries = entries or EntryPoints()

    def site(self, file, call) -> ChannelSite | None:
        fn = call.child_by_field_name('function')
        if fn is None:
            return None
        if fn.type == 'field_expression':
            entry = self._on_value(file, fn)
            offset = 0
        elif fn.type == 'scoped_identifier':
            entry = self._on_type(file, fn)
            offset = 1 if entry is not None and entry.instance else 0  # `UdpSocket::send_to(&socket, buf, addr)`
        else:
            return None
        args = RustSyntax.args(call)
        if entry is None or entry.argument + offset >= len(args):
            return None
        return ChannelSite(entry, call, args[entry.argument + offset])

    def _on_value(self, file, fn):
        entries = self._entries.named(RustSyntax.text(fn.child_by_field_name('field')), True)
        if not entries:
            return None
        path = self._types.of(file, fn.child_by_field_name('value'))
        return EntryPoints.match(entries, path) if path else None

    def _on_type(self, file, fn):
        segs = ItemPath.imported(file, fn)
        if len(segs) < 2:
            return None
        entries = self._entries.named(segs[-1], False) + self._entries.named(segs[-1], True)
        return EntryPoints.match(entries, '::'.join(segs[:-1]))
