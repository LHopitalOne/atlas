"""One route per declaration, whichever collector or router found it."""


class UniqueRoutes:
    """Routes are the same when they share file, path, methods and handler: trailing-slash variants registered on
    their own lines, or a router reachable from two roots. The first one found wins: routers are evaluated in
    source order, then attribute routes, so the result is deterministic."""

    @staticmethod
    def key(route):
        return (route.file, str(route.path), route.methods, route.handler)

    @classmethod
    def first(cls, routes) -> list:
        seen, out = set(), []
        for r in routes:
            k = cls.key(r)
            if k not in seen:
                seen.add(k)
                out.append(r)
        return out
