"""What a file does, in words: a summary, its role in the system and a few domain tags, written by a model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Description:
    """One file described: `summary` is one plain sentence, `role` one of ROLES, `tags` a few lowercase words."""

    summary: str
    role: str
    tags: tuple[str, ...] = ()

    ROLES = ('api', 'frontend', 'worker', 'client', 'data', 'auth', 'config', 'test', 'tooling', 'other')
