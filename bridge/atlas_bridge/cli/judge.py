"""The --jev step: Jev chooses among the routes the code leaves open, and says what it did and what it cost."""

from ..adapters.jev import JevRouteJudge
from ..usecases.judged import JudgedLinks


class JudgePass:
    def __init__(self, report):
        self._report = report

    def run(self, links, extraction, folders, include_tests=False, within=False):
        judge = JevRouteJudge(folders)
        judged = JudgedLinks(judge, include_tests, within)
        out = judged.refine(links, extraction)
        r = judged.report
        failed = f', {len(judge.failures)} requests failed' if judge.failures else ''
        self._report(
            f'  jev       asked about {r.asked} open requests, settled {r.settled} (${judge.cost:.4f}{failed})'
        )
        return out
