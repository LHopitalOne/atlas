"""What one file declares about routes: the routes of its routers, and the routers it mounts under a prefix."""


class FileRoutes:
    """The route declarations and mounts of one file, with the JsModule they were read from."""

    def __init__(self, module):
        self._module = module
        self._routes = []
        self._mounts = []

    @property
    def module(self):
        return self._module

    @property
    def path(self):
        return self._module.path

    @property
    def routes(self) -> list:
        """[RouteDeclaration], in source order."""
        return list(self._routes)

    @property
    def mounts(self) -> list:
        """[Mount], in source order."""
        return list(self._mounts)

    def add_route(self, route):
        self._routes.append(route)

    def add_mount(self, mount):
        self._mounts.append(mount)

    def __bool__(self):
        return bool(self._routes or self._mounts)
