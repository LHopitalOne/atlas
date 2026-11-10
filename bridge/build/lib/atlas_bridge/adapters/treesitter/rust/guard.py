"""Containing a stack overflow to the piece of extraction that caused it."""


class StackGuard:
    """Runs one piece of extraction so that an absurdly nested input that still exhausts the stack costs only that
    piece: one file must not stop the repository."""

    @staticmethod
    def run(fn, *args):
        try:
            return fn(*args)
        except RecursionError:
            return []
