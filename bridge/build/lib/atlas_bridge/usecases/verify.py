"""Use case: check what each link rests on against a precise index (SCIP), through the DefinitionOracle port."""

from dataclasses import replace

from ..core.evidence import Verdict, Verification
from ..core.model import Status
from .link import Link
from .ports import DefinitionOracle


class LinkVerifier:
    """Marks each matched link confirmed, syntax, contradicted or unverified.

    Only a matched link (a named service and one route that fits) can be confirmed: an inferred, ambiguous or
    unmatched link is a guess about the target, which no index of the caller's code can settle. A matched link is
    confirmed when every name it rests on resolves, in the caller's index, to the definition the finder assumed; one
    that rests on no name lookup at all is marked syntax, since there is nothing for the index to confirm. What the
    index cannot judge is configuration: which host a base URL points to at run time.
    """

    def __init__(self, oracle: DefinitionOracle):
        self._oracle = oracle

    def verify(self, links: list[Link]) -> list[Link]:
        return [self._verify(link) for link in links]

    def _verify(self, link: Link) -> Link:
        if link.status is not Status.MATCHED or link.call.is_payload or not self._oracle.covers(link.call.repo):
            return link
        verdicts = tuple((a, self._oracle.check(link.call.repo, a)) for a in link.call.assumptions)
        return replace(link, verification=Verification.of(v for _, v in verdicts), verdicts=verdicts)

    @staticmethod
    def count(links: list[Link]) -> dict:
        """{verification value: number of links}, plus how many assumptions each verdict got."""
        out = {v.value: sum(link.verification is v for link in links) for v in Verification}
        for verdict in Verdict:
            out[f'assumptions_{verdict.value}'] = sum(v is verdict for link in links for _, v in link.verdicts)
        return out
