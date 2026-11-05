"""`app.use('/prefix', router)`: a router mounted under a prefix."""

from ..syntax.nodes import JsSyntax
from .records import Mount
from .syntax import DeclarationSyntax


class MountSyntax(DeclarationSyntax):
    """`parent.use('/prefix', child)`; `app.use(middleware)` (no prefix) mounts nothing."""

    def declaration(self, site):
        args = site.args
        if len(args) < 2 or not self.is_string(args[0]):
            return None
        prefix = JsSyntax.string(JsSyntax.unwrap(args[0]))
        return Mount(JsSyntax.text(site.receiver), prefix, JsSyntax.unwrap(args[-1]))
