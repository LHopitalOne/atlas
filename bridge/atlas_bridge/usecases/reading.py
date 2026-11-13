"""Use case helper: check what a language model says a file sends or serves against the file's own code, before it is
matched.

The model reads; the code decides what it may claim. A claim the file does not bear out is dropped, so a model that
invents a URL, a line or a service name adds nothing.
"""

import re
from difflib import SequenceMatcher

from ..core.http import ANY, Call, PathTemplate, Protocol, Route
from .ports import ReadCase, ReadHelper, ReadRequest, ReadRoute


class ReadUrl:
    """A URL as a reader writes it, split into host, base expressions and path: 'https://api.x.com/v1/items',
    '{settings.api_url}/users/{id}', '{API_HOST}{API_PATH}/users' (base: the first expression; bases: each),
    '/api/orders', or, for a channel, a bare name ('orders.created'). A channel named
    by a member of a constant class ('JobName.SendMail') is that member's name, however either side spells the
    class; a route's own parameter syntax ('<int:pk>', ':id') is written '{pk}'."""

    TEMPLATE = re.compile(r'\$\{([^{}]*)\}')  # a JavaScript template's '${x}' is written '{x}'
    ABSOLUTE = re.compile(r'^(?:[a-z][a-z0-9+.-]*:)?//(?P<host>[^/?#{}:]+)(?::\d+)?(?P<path>/[^#]*)?$', re.IGNORECASE)
    BASED = re.compile(r'^(?P<bases>(?:\{[^{}]+\})+)(?P<path>/[^#]*)?$')  # '{API_URL}/users', '{host}{prefix}/users'
    EXPRESSION = re.compile(r'\{(?P<expression>[^{}]+)\}')
    CHANNEL = re.compile(r'^\{?(?P<name>[\w.:-]+)\}?$')  # 'orders.created', 'mail:send', '{JobName.SendMail}'
    MEMBER = re.compile(r'^[A-Z]\w*\.(?P<member>[A-Za-z_]\w*)$')  # 'JobName.SendMail', not 'orders.created'
    ROUTE_PARAM = re.compile(r'<(?:[^<>:]*:)?(?P<name>[^<>:]+)>|(?<=/):(?P<colon>\w+)')  # '<int:pk>', '<id>', ':id'

    def __init__(self, url: str, protocol: str):
        text = self.TEMPLATE.sub(r'{\1}', (url or '').strip()).split('#')[0]
        self.host, self.base, self.path, self.name = '', '', '', ''
        self.bases: tuple[str, ...] = ()
        absolute, based, channel = self.ABSOLUTE.match(text), self.BASED.match(text), self.CHANNEL.match(text)
        if protocol != Protocol.HTTP and channel:
            self.name = channel.group('name')
            member = self.MEMBER.match(self.name)
            self.path = '/' + (member.group('member') if member else self.name)
        elif absolute:
            self.host, self.path = absolute.group('host').lower(), absolute.group('path') or '/'
        elif based:
            self.bases = tuple(e.strip() for e in self.EXPRESSION.findall(based.group('bases')))
            self.base, self.path = self.bases[0], based.group('path') or ''
        elif text.startswith('/'):
            self.path = text

    @classmethod
    def route(cls, path: str, protocol: str) -> str:
        """A route path or channel as a reader writes it, in the canonical syntax ('' when it is not one)."""
        text = cls.ROUTE_PARAM.sub(lambda m: '{' + (m.group('name') or m.group('colon')) + '}', (path or '').strip())
        if protocol != Protocol.HTTP:
            return cls(text, protocol).path
        text = text.lstrip('^').rstrip('$')  # a Django regex route, '^api/items/$'
        if not text or '://' in text or text.startswith('{'):
            return ''
        return text if text.startswith('/') else '/' + text


class ReadCheck:
    """Turns a request a reader claims into a Call, or None when the code does not bear it out:

    - the quoted code is on the line the reader names, or within NEAR lines of it (most of it, SAME of the shorter
      of the two, when the reader adds words of its own), or exactly on one line of the file (the call is placed
      where the code really is);
    - the protocol is one Atlas knows, the URL holds a path, and every fixed word of the path is written in the file
      or in the URL of the helper the request goes through;
    - an absolute URL's host must be written in the file; the base expression, the service words and the enclosing
      function count only when the file (or the helper) writes them.
    """

    NEAR = 3  # lines a quote may sit from the line the reader names
    MIN_QUOTE = 6  # characters of code a quote must hold to place a line
    SAME = 0.6  # the share of the shorter of a quote and a line their longest common run must cover
    MIN_RUN = 12  # characters that run must hold
    METHODS = frozenset({'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'})
    WORD = re.compile(r'[A-Za-z][A-Za-z0-9]+')
    METHOD_SEP = re.compile(r'[\s,|/]+')  # 'GET, POST', 'GET|POST'
    QUOTES = '"\'`'
    # a link a person clicks (<a href>, a Hyperlink's destination, <Link to>) or a redirect a server answers with:
    # where a browser may go next, not a request the code sends
    CLICKED = re.compile(
        r'(?<!location\.)\bhref\s*[=:]|\bdestination\s*[=:]|<Link\b|\bredirect\s*\(|\b\w*Redirect(?:Response)?\s*\('
    )
    MIN_ROUTE_WORDS = 2  # fixed words an HTTP route read needs: a bare '/courses' may be a fragment of a longer path
    NAME = re.compile(r'^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$')  # 'create_account', 'Client.create'

    def call(self, case: ReadCase, request: ReadRequest) -> Call | None:
        protocol = (request.protocol or '').lower()
        if protocol not in Protocol.ALL:
            return None
        line = self.placed(case.text, request.line, request.code)
        if line is None or self.CLICKED.search(case.text.splitlines()[line - 1]):
            return None
        url = ReadUrl(request.url, protocol)
        helper = self._helper(case, request.through)
        written = case.text.lower() + '\n' + (helper.url.lower() if helper else '')
        path = PathTemplate.parse(url.path) if url.path else None
        if path is None or not path.literals or not self.fixed_words_written(path, written):
            return None
        if url.host and url.host not in written or not self.named(url, case.text):
            return None
        hints = self._hints(request, url, written)
        method = request.method.upper() if protocol == Protocol.HTTP else ANY
        function = request.function if self.NAME.match(request.function or '') and request.function in case.text else ''
        return Call(
            case.repo,
            case.path,
            line,
            path,
            method if method in self.METHODS else ANY,
            function,
            frozenset(hints),
            protocol=protocol,
        )

    @classmethod
    def named(cls, url: ReadUrl, text: str) -> bool:
        """A channel the code names: a quoted string ('emails') or a constant's member (JobName.SendMail), not a
        variable that holds one (queueName, event), which would meet every other such variable."""
        if not url.name or ReadUrl.MEMBER.match(url.name):
            return True
        return any(f'{q}{url.name}{q}' in text for q in cls.QUOTES)

    def route(self, case: ReadCase, route: ReadRoute) -> Route | None:
        """The route a reader claims a file serves, or None when the code does not bear it out: the declaring line is
        placed as a request's is, every fixed word of the path is written in the file, and one is written within NEAR
        lines of the declaration (a relay that takes every event, `server.on(event, ...)`, declares none)."""
        protocol = (route.protocol or '').lower()
        line = self.placed(case.text, route.line, route.code) if protocol in Protocol.ALL else None
        path = ReadUrl.route(route.path, protocol) if line is not None else ''
        template = PathTemplate.parse(path) if path else None
        if template is None or not self.fixed_words_written(template, case.text.lower()):
            return None
        if protocol == Protocol.HTTP and template.fixed < self.MIN_ROUTE_WORDS:
            return None
        around = '\n'.join(case.text.splitlines()[max(0, line - 1 - self.NEAR) : line + self.NEAR]).lower()
        if not any(s.text in around for s in template.segments if s.is_literal):
            return None
        if protocol != Protocol.HTTP and (
            not template.literals or not self.named(ReadUrl(route.path, protocol), case.text)
        ):
            return None
        methods = {m for m in self.METHOD_SEP.split(route.method.upper()) if m in self.METHODS}
        handler = route.function if self.NAME.match(route.function or '') and route.function in case.text else ''
        return Route(case.repo, case.path, line, template, frozenset(methods or {ANY}), handler, '', 'read', protocol)

    def helper_ok(self, case: ReadCase, helper: ReadHelper) -> bool:
        """A helper worth telling other files about: its name is written in its file; a function's URL has a fixed
        word, every one written in the file, or is all parameters behind a base the file writes (a wrapper its callers
        pass the path to: '{API_BASE}/{endpoint}/'); a client's base is an expression or URL the file writes."""
        if not self.NAME.match(helper.function or '') or helper.name not in case.text:
            return False
        url, text = ReadUrl(helper.url, Protocol.HTTP), case.text.lower()
        if helper.kind == ReadHelper.CLIENT:
            base = url.host or url.base
            return bool(base) and base.lower() in text
        path = PathTemplate.parse(url.path) if url.path else None
        if path is None:
            return False
        if path.literals:
            return self.fixed_words_written(path, text)
        return any(b.lower() in text for b in (url.host, *url.bases) if b)

    def placed(self, text: str, line: int, code: str) -> int | None:
        """The line the quoted code is on: the nearest to `line` within NEAR, else the only one in the file."""
        quote = next((self._flat(q) for q in (code or '').splitlines() if q.strip()), '')
        if len(quote) < self.MIN_QUOTE:
            return None
        lines = [self._flat(t) for t in text.splitlines()]
        near = sorted(
            range(max(0, line - 1 - self.NEAR), min(len(lines), line + self.NEAR)), key=lambda i: abs(i + 1 - line)
        )
        hit = next((i for i in near if quote in lines[i]), None)
        if hit is None:
            hit = next((i for i in near if self._alike(quote, lines[i])), None)
        if hit is None:
            hits = [i for i, t in enumerate(lines) if quote in t]
            hit = hits[0] if len(hits) == 1 else None
        return None if hit is None else hit + 1

    @staticmethod
    def fixed_words_written(path: PathTemplate, written: str) -> bool:
        return all(s.text.lower() in written for s in path.segments if s.is_literal)

    def _alike(self, quote, line):
        if len(line) < self.MIN_QUOTE:
            return False
        run = SequenceMatcher(None, quote, line, autojunk=False).find_longest_match().size
        return run >= self.MIN_RUN and run >= self.SAME * min(len(quote), len(line))

    @staticmethod
    def _helper(case, through):
        """The helper a request goes through: 'getSeries', 'Client.get_charge', or a client's method ('http.get')."""
        parts = set((through or '').split('.'))
        return next((h for h in case.helpers if through == h.function or h.name in parts), None)

    def _hints(self, request, url, written):
        hints = {Call.ORIGIN + url.host} if url.host else set()
        hints |= {b for b in url.bases if b.lower() in written}
        base = request.base.strip('{}$ ')
        if base and base.lower() in written:
            hints.add(base)
        hints |= {w for w in self.WORD.findall(request.service or '') if w.lower() in written}
        return hints

    @staticmethod
    def _flat(text):
        return ' '.join(text.split())
