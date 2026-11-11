"""The --read step: a language model reads the files the extractors leave unexplained for the requests they send;
the code checks each claim and matches it with the same rules, and the run says what it found and what it cost."""

from collections.abc import Callable
from typing import NamedTuple

from ..adapters.muse import MuseReader
from ..adapters.treesitter.kit import RepositorySources
from ..usecases.channels import OwnChannelRule
from ..usecases.link import LinkFinder
from ..usecases.outside import OutsideRule
from ..usecases.read import ReadFinders, ReadLinks
from ..usecases.within import ReadWithinRule, WithinRepoRule


class ReadOptions(NamedTuple):
    aliases: dict
    include_tests: bool
    within: bool
    is_test: Callable[[str], bool]
    model: str | None = None


class ReadPass:
    def __init__(self, report):
        self._report = report

    def run(self, links, extraction, folders, options):
        """The links with those the reader found added (options: ReadOptions)."""
        reader = MuseReader(options.model)
        names, aliases, tests = list(folders), options.aliases, options.include_tests
        own, read_own = (WithinRepoRule, ReadWithinRule) if options.within else ((), ())
        finders = ReadFinders(
            LinkFinder(names, aliases, tests, self.rules(own)),
            LinkFinder(names, aliases, tests, self.rules(read_own), (OutsideRule,)),
        )
        sources = RepositorySources(folders, options.is_test)
        read = ReadLinks(reader, sources, finders, names)
        out = read.refine(links, extraction)
        r = read.report
        failed = f', {len(reader.failures)} requests failed' if reader.failures else ''
        self._report(
            f'  read      {reader.model} read {r.files} files ({r.again} again with their helpers): {r.claimed} '
            f'requests claimed, {r.checked} borne out by the code, {r.routes} routes read, {r.linked} requests linked '
            f'(${reader.cost:.4f}{failed})'
        )
        return out

    @staticmethod
    def rules(within):
        """The rules of `links`, with `within` (a rule for browser code calling its own server, or none) after a
        task its own repository handles and before a path alone."""
        *before, path_only = LinkFinder.RULES
        return (*before, OwnChannelRule, *((within,) if within else ()), path_only)
