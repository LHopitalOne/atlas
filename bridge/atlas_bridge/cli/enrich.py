"""The --enrich step: a small model says what each file does, and the run says how many and what it cost."""

from ..adapters.muse import MuseDescriber
from ..adapters.treesitter.kit import TestPathPolicy
from ..core.errors import BridgeError
from ..usecases.enrich import Enricher


class EnrichPass:
    def __init__(self, report):
        self._report = report

    def run(self, graph, folders, linked=frozenset()):
        """{(repo, path): Description}, and the model that wrote them; ({}, '') when it cannot be asked."""
        try:
            describer = MuseDescriber(folders)
            enricher = Enricher(describer, TestPathPolicy().is_test)
            found = enricher.describe(graph, linked)
        except BridgeError as e:
            self._report(f'  enrich    no descriptions: {e}')
            return {}, ''
        r = enricher.report
        failed = f', {len(describer.failures)} requests failed' if describer.failures else ''
        self._report(
            f'  enrich    {describer.model} described {r.described} of {r.asked} files (${describer.cost:.4f}{failed})'
        )
        return found, describer.model
