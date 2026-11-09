"""ScipOracle: the DefinitionOracle port answered from SCIP indexes, one or more per repository."""

from ...core.evidence import Assumption, Verdict
from ...usecases.ports import DefinitionOracle
from .index import ScipIndex
from .symbol import ScipSymbol


class ScipOracle(DefinitionOracle):
    def __init__(self, indexes: dict[str, list[ScipIndex]]):
        self._indexes = indexes

    def covers(self, repo: str) -> bool:
        return bool(self._indexes.get(repo))

    def check(self, repo: str, assumption: Assumption) -> Verdict:
        """Confirmed when the name on that line resolves to a definition inside the assumed range (or, with no
        target, to any definition in the repository); contradicted when it resolves only to other definitions in the
        repository; unknown when the index has nothing on that line by that name, or only outside definitions."""
        repo = assumption.repo or repo
        if assumption.target_repo and assumption.target_repo != repo:
            return self._across(repo, assumption)
        verdicts = [self._check(index, assumption) for index in self._indexes.get(repo, [])]
        return self._strongest(verdicts)

    def _across(self, repo, a):
        """A call into another repository read alongside (a library): confirmed when the name on that line resolves
        to a definition in the assumed range there, compared by ScipSymbol.key since the two indexes may write the
        package and module path differently."""
        keys = {
            ScipSymbol.key(o.symbol)
            for index in self._indexes.get(repo, [])
            for o in index.at(a.file, a.line)
            if ScipSymbol.name(o.symbol) == a.name
        }
        if not keys:
            return Verdict.UNKNOWN
        targets = [index.document(a.target_file) for index in self._indexes.get(a.target_repo, [])]
        defined = {
            ScipSymbol.key(o.symbol)
            for doc in targets
            if doc is not None
            for o in doc.definitions()
            if a.target_start <= o.line <= a.target_end
        }
        if keys & defined:
            return Verdict.CONFIRMED
        return Verdict.CONTRADICTED if any(doc is not None for doc in targets) else Verdict.UNKNOWN

    @staticmethod
    def _strongest(verdicts):
        for verdict in (Verdict.CONFIRMED, Verdict.CONTRADICTED):
            if verdict in verdicts:
                return verdict
        return Verdict.UNKNOWN

    @staticmethod
    def _check(index, a):
        symbols = {o.symbol for o in index.at(a.file, a.line) if ScipSymbol.name(o.symbol) == a.name}
        if not symbols:
            return Verdict.UNKNOWN
        if a.has_target and any(index.defined_in(s, a.target_file, a.target_start, a.target_end) for s in symbols):
            return Verdict.CONFIRMED
        found = [d for s in symbols for d in index.definitions(s)]
        if any(a.covers(path, line) for path, line in found):
            return Verdict.CONFIRMED
        return Verdict.CONTRADICTED if found else Verdict.UNKNOWN
