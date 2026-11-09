"""Use case: receivers of broker channels declared in configuration rather than code, found where another repository
names the channel."""

import re

from ..core.http import PathTemplate, Protocol, Route
from .ports import ChannelMentions


class NamedChannels:
    """A topic, queue or pub/sub channel is one name on the whole broker, so a repository that names a channel some
    other repository sends to, and does not send to it itself, most likely consumes it: its consumer is often wired
    in a registry, a YAML file or a command line rather than in a library call. Each such repository gets one route
    for the channel, at the mention that looks most like a consumer's (a reader's words around it and not a
    writer's, a config file); the link it makes is inferred, never matched."""

    BROKERS = frozenset({Protocol.KAFKA, Protocol.AMQP, Protocol.REDIS})
    READING = re.compile(
        r'consum|subscri|stream|loader|processor|listen|reader|receiv|handler', re.I
    )  # a consumer's words
    WRITING = re.compile(r'produc|publish|\bsend|emit|writer', re.I)  # a producer's words
    CONFIG = re.compile(r'\.(ya?ml|json|toml|ini|cfg|env)$', re.I)
    FRAMEWORK = 'named'  # Route.framework of a receiver found by its name

    def __init__(self, mentions: ChannelMentions, repos):
        self._mentions = mentions
        self._repos = list(repos)

    def routes(self, calls, routes) -> list[Route]:
        """The routes to add: one per (repository, broker channel) named there by a repository that does not send to
        it and has no route for it yet."""
        senders, known = {}, {(r.repo, r.protocol, str(r.path)) for r in routes}
        for c in calls:
            if c.protocol in self.BROKERS and c.path is not None and not c.test and c.path.size == 1:
                senders.setdefault((c.protocol, str(c.path)), set()).add(c.repo)
        out = []
        for (protocol, path), sending in sorted(senders.items()):
            for repo in self._repos:
                if repo not in sending and (repo, protocol, path) not in known:
                    out += self._named(repo, protocol, path)
        return out

    def _named(self, repo, protocol, path):
        name = path.lstrip('/')
        best = max(self._mentions.mentions(repo, name), key=self._weight, default=None)
        if best is None or not self._weight(best):
            return []
        file, line, _ = best
        return [
            Route(repo, file, line, PathTemplate.parse(path), handler=name, framework=self.FRAMEWORK, protocol=protocol)
        ]

    def _weight(self, mention):
        """0 unless the words around the mention (or its file's path) are a reader's rather than a writer's: a topic
        name in a producer's settings is not a consumer. More for a reader's word on the lines themselves, and for a
        config file."""
        file, _, around = mention
        reads = bool(self.READING.search(around)) + bool(self.READING.search(file))
        writes = bool(self.WRITING.search(around)) + bool(self.WRITING.search(file))
        if not reads or writes >= reads:
            return 0
        return 1 + bool(self.READING.search(around)) + bool(self.CONFIG.search(file))
