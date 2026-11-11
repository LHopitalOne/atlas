"""Use case helper: which files a reader is asked about (usecases.read), and which again with the helpers they call."""

import re

from .ports import ReadCase, ReadHelper, SourceFiles
from .reading import ReadCheck


class ReadFiles:
    """1. The files that look like they talk to the network (SIGNAL) or serve routes, jobs or messages
    (ROUTE_SIGNAL), with more such code than the extractors explained there (requests linked, routes read).
    2. The files that call a helper another file defines (a function that sends a request built from its parameters,
    or a client made with a base URL), with the helpers they call."""

    MAX_FILES = 1500  # files read in one run, to bound cost and time
    MAX_AGAIN = 400  # files read a second time with the helpers they call
    MAX_HELPERS = 6  # helpers listed to one file
    MAX_CALLERS = 60  # files a helper may be called from before its name says too little ('send', 'request')
    MIN_HELPER_NAME = 4  # characters a helper's name needs to be looked for in other files
    SIGNAL = re.compile(
        r'\b(?:fetch|axios|ajax|XMLHttpRequest|requests|httpx|aiohttp|urlopen|urllib|reqwest|HttpClient|RestTemplate'
        r'|WebClient|WebSocket|EventSource|http\.(?:Get|Post|NewRequest)|session\.(?:get|post|put|patch|delete|request)'
        r'|location\.(?:assign|replace|href)|window\.open|send_task|apply_async|basic_publish|publish|enqueue|produce'
        r'|\.request|\.(?:get|post|put|patch|delete)\s*(?:<[^()]*>)?\()'
    )
    # decorators and registrations that declare a route, a job or task handler, or a message consumer
    ROUTE_SIGNAL = re.compile(
        r'@(?:[\w.]+\.)?(?:route|get|post|put|patch|delete|websocket|api_view|action|task|shared_task|receiver'
        r'|Get|Post|Put|Patch|Delete|All|Controller|OnJob|Process|Processor|OnEvent|EventPattern|MessagePattern'
        r'|SubscribeMessage|KafkaListener|RabbitListener|RequestMapping|GetMapping|PostMapping)\b'
        r'|\burlpatterns\b|\badd_url_rule\b|\.register\(|\b(?:consume|subscribe|basic_consume)\s*\(|\bnew Worker\('
    )
    FUNCTION_CALL = re.compile(r'\b([A-Za-z_$][\w$]*)\s*\(')  # a helper function called: 'send_to_bouncer('
    METHOD_CALL = re.compile(r'\b([A-Za-z_$][\w$]*)\s*\.\s*[\w$]+\s*(?:<[^()]*>)?\s*\(')  # a client's: 'http.get<T>('

    def __init__(self, sources: SourceFiles, repos: list[str]):
        self._sources = sources
        self._repos = repos
        self._check = ReadCheck()

    def first(self, linked: dict, served: dict) -> list[ReadCase]:
        """The files to read first. linked, served: {(repo, path): requests linked, routes read there}."""
        picked = []
        for repo in self._repos:
            for path in self._sources.paths(repo):
                text = self._sources.text(repo, path)
                if not text:
                    continue
                sends = len(self.SIGNAL.findall(text)) - linked.get((repo, path), 0)
                serves = len(self.ROUTE_SIGNAL.findall(text)) - served.get((repo, path), 0)
                if sends > 0 or serves > 0:
                    picked.append((-max(sends, 0) - max(serves, 0), repo, path, text))
        picked.sort(key=lambda p: p[:3])
        return [ReadCase(repo, path, text) for _, repo, path, text in picked[: self.MAX_FILES]]

    def again(self, cases, readings, done) -> list[ReadCase]:
        """The files that call a helper another file defines, with the helpers they call. A function whose own
        request already settled (`done`: (repo, path, function name)) is no helper: its link is drawn where it
        sends."""
        out = []
        for repo, defined in self._helpers(cases, readings, done).items():
            callers = self._callers(repo, defined)
            out += [
                ReadCase(repo, path, text, used[: self.MAX_HELPERS]) for path, (text, used) in sorted(callers.items())
            ]
        return out[: self.MAX_AGAIN]

    def _helpers(self, cases, readings, done):
        """{repo: [(defining path, helper)]}: the helpers the code bears out, with names long enough to look for."""
        found = {}
        for case, reading in zip(cases, readings, strict=True):
            for h in reading.helpers if reading else ():
                if h.kind == ReadHelper.FUNCTION and (case.repo, case.path, h.name) in done:
                    continue
                if len(h.name) >= self.MIN_HELPER_NAME and self._check.helper_ok(case, h):
                    found.setdefault(case.repo, []).append((case.path, h))
        return found

    def _callers(self, repo, defined):
        """{path: (text, helpers it calls)} for the repository's files that call a helper defined in another file,
        leaving out helpers called from more than MAX_CALLERS files."""
        callers = {}
        for path in self._sources.paths(repo):
            text = self._sources.text(repo, path)
            called = {
                ReadHelper.FUNCTION: set(self.FUNCTION_CALL.findall(text)),
                ReadHelper.CLIENT: set(self.METHOD_CALL.findall(text)),
            }
            used = tuple(h for at, h in defined if at != path and h.name in called[h.kind])
            if used:
                callers[path] = (text, used)
        counts = {}
        for _, used in callers.values():
            for h in {u.function for u in used}:
                counts[h] = counts.get(h, 0) + 1
        common = {h for h, n in counts.items() if n > self.MAX_CALLERS}
        callers = {p: (t, tuple(u for u in used if u.function not in common)) for p, (t, used) in callers.items()}
        return {p: (t, used) for p, (t, used) in callers.items() if used}
