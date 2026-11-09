"""Where a channel expression is resolved: its file and, inside a followed fn, the arguments of the call."""

from typing import NamedTuple


class Frame(NamedTuple):
    """The arguments one call passes to a crate fn, while its body is read for the value it returns."""

    fn: tuple  # the key of the fn (RustFile.key) whose parameters these are
    args: dict  # parameter name -> argument node
    caller: 'ChannelScope'  # where the arguments are resolved


class ChannelScope(NamedTuple):
    """A ValueScope that may carry a Frame: the parameters of the fn being followed are its call's arguments."""

    file: object
    join: bool = False
    frame: Frame | None = None

    def joined(self, join=True):
        return self if join == self.join else self._replace(join=join)

    def moved(self, file):
        return self if file is self.file else self._replace(file=file, frame=None)

    def argument(self, key, name):
        """The argument a call passes for parameter `name` of fn `key`, as (node, scope), or None outside it."""
        if self.frame is None or self.frame.fn != key or name not in self.frame.args:
            return None
        return self.frame.args[name], self.frame.caller
