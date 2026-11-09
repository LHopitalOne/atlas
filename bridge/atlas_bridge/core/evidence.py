"""What a link rests on: the names the finder resolved without a compiler, and what a precise index says of them."""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Assumption:
    """`name`, used at `file:line`, was taken to mean a definition in `target_file` between `target_start` and
    `target_end` (inclusive). With no target_file it was only taken to be defined somewhere in the repository
    (a trait or class of its own, not one from a library). `repo` and `target_repo` place a call that crosses into a
    library read alongside the services."""

    file: str
    line: int
    name: str
    target_file: str = ''
    target_start: int = 0
    target_end: int = 0
    repo: str = ''  # the repository `file` is in, when not the one the link starts from (a library on the way)
    target_repo: str = ''  # the repository `target_file` is in, when not `repo` (a call into a library)

    @property
    def has_target(self):
        return bool(self.target_file)

    def covers(self, file: str, line: int) -> bool:
        """Whether a definition at file:line is the one assumed."""
        if not self.has_target:
            return True
        return file == self.target_file and self.target_start <= line <= self.target_end


class Verdict(Enum):
    """What a precise index says of one assumption."""

    CONFIRMED = 'confirmed'  # the name at that line resolves to the assumed definition
    CONTRADICTED = 'contradicted'  # it resolves, but to a different definition
    UNKNOWN = 'unknown'  # the index has no resolution for that name at that line


class Verification(Enum):
    """What a precise index says of a whole link, from the verdicts on everything it rests on."""

    CONFIRMED = 'confirmed'  # it rests on names, and the index confirms every one
    SYNTAX = 'syntax'  # it rests on no name lookup at all: read straight from the code, nothing for an index to check
    CONTRADICTED = 'contradicted'  # at least one assumption is wrong
    UNVERIFIED = 'unverified'  # no index for the repository, some names unresolved, or not a matched link

    @classmethod
    def of(cls, verdicts) -> 'Verification':
        verdicts = list(verdicts)
        if not verdicts:
            return cls.SYNTAX
        if Verdict.CONTRADICTED in verdicts:
            return cls.CONTRADICTED
        if all(v is Verdict.CONFIRMED for v in verdicts):
            return cls.CONFIRMED
        return cls.UNVERIFIED
