"""The order calls are reported in."""


class CallOrder:
    """File by file, in the order the files were given; within a file, in the order the collectors found them
    (request-trait impls, then client calls). The sort is stable, so this is the order of a per-file walk."""

    def __init__(self, paths):
        self._rank = {p: i for i, p in enumerate(paths)}

    def sorted(self, calls) -> list:
        return sorted(calls, key=lambda c: self._rank.get(c.file, len(self._rank)))
