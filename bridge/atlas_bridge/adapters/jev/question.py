"""What Jev is shown about one request, and how its answer is read back."""

import os

from ...usecases.ports import Choice, JudgeCase


class RouteQuestion:
    """The state Jev reads (the request as the code writes it, the lines around it, the candidate routes) and the one
    `choice` question it answers: which route receives the request, or none."""

    CONTEXT = 6  # lines shown before and after the call
    MAX_LINE = 160  # a longer line is cut: minified or generated code says nothing more
    MAX_HINTS = 12
    NONE = 'none'
    INSTRUCTIONS = (
        'A static analysis tool read this request in the source code but could not tell for sure which route '
        'receives it. Which of the candidate routes handles this request when the code runs? Read the code around '
        'the call: the URL or path it builds, the client or base URL it uses, the method. Answer none if it is sent '
        'somewhere else (another service not listed, a third-party site), or if the code does not show enough to tell.'
    )

    def __init__(self, folders: dict[str, str]):
        self._folders = folders
        self._lines: dict[tuple[str, str], list[str]] = {}

    def state(self, case: JudgeCase) -> dict:
        call = case.call
        return {
            'request': {
                'repository': call.repo,
                'at': f'{call.file}:{call.line}',
                'function': call.function,
                'protocol': call.protocol,
                'method': call.method,
                'path as read from the code ({...} is a value the code fills in)': str(call.path),
                'names near the call': sorted(call.hints)[: self.MAX_HINTS],
                'code around the call (>> marks its line)': self._code(call.repo, call.file, call.line),
            },
            'candidate routes': {self.key(i): self._route(r) for i, r in enumerate(case.candidates)},
        }

    def questions(self, case: JudgeCase) -> dict:
        criteria = {self.key(i): self._label(r) for i, r in enumerate(case.candidates)}
        criteria[self.NONE] = 'none of these routes receives it, or the code does not show enough to tell'
        return {'route': {'type': 'choice', 'instructions': self.INSTRUCTIONS, 'criteria': criteria}}

    def choice(self, case: JudgeCase, answers: dict) -> Choice:
        answer = answers.get('route') or {}
        picked = answer.get('choice')
        probability = float((answer.get('probabilities') or {}).get(picked, 0.0))
        if picked == self.NONE or picked not in {self.key(i) for i in range(len(case.candidates))}:
            return Choice(None, probability)
        return Choice(int(picked[1:]) - 1, probability)

    @staticmethod
    def key(i: int) -> str:
        return f'r{i + 1}'

    @staticmethod
    def _label(route) -> str:
        methods = '|'.join(sorted(route.methods))
        handler = f', handled by {route.handler}' if route.handler else ''
        return f'{route.repo}: {methods} {route.path}{handler} ({route.file}:{route.line})'

    def _route(self, route) -> dict:
        return {
            'repository': route.repo,
            'methods': sorted(route.methods),
            'path': str(route.path),
            'handler': route.handler,
            'declared at': f'{route.file}:{route.line}',
            'code': self._code(route.repo, route.file, route.line, before=1, after=3),
        }

    def _code(self, repo, file, line, before=CONTEXT, after=CONTEXT) -> str:
        lines = self._read(repo, file)
        if not lines or line < 1:
            return ''
        start, end = max(1, line - before), min(len(lines), line + after)
        out = []
        for n in range(start, end + 1):
            mark = '>>' if n == line else '  '
            out.append(f'{mark}{n:5} {lines[n - 1][: self.MAX_LINE]}')
        return '\n'.join(out)

    def _read(self, repo, file):
        key = (repo, file)
        if key not in self._lines:
            folder = self._folders.get(repo)
            try:
                with open(os.path.join(folder, file), encoding='utf-8', errors='replace') as f:
                    self._lines[key] = f.read().splitlines()
            except (OSError, TypeError):
                self._lines[key] = []
        return self._lines[key]
