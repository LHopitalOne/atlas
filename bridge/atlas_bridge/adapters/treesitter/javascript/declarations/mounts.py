"""`app.use('/prefix', router)` and Fastify's `app.register(plugin, { prefix: '/prefix' })`: a router mounted under a
prefix."""

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


class RegisterSyntax(DeclarationSyntax):
    """Fastify's `parent.register(plugin, { prefix: '/prefix' })`; a plugin registered with no prefix option mounts
    nothing to prefix."""

    def declaration(self, site):
        args = site.args
        options = JsSyntax.unwrap(args[1]) if len(args) >= 2 else None
        prefix = JsSyntax.prop(options, 'prefix') if options is not None and options.type == 'object' else None
        if prefix is None or not self.is_string(prefix):
            return None
        return Mount(JsSyntax.text(site.receiver), JsSyntax.string(JsSyntax.unwrap(prefix)), JsSyntax.unwrap(args[0]))
