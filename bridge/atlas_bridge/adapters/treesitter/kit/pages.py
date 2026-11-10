"""Resources a page loads from other sites: scripts, stylesheets, images and frames in HTML templates."""

import re

from ....core.errors import SourceReadError
from ....core.http import Call, PathTemplate
from .files import RepositoryFiles, TestPathPolicy
from .strings import UrlTemplate


class PageTags:
    """`<script src="https://telegram.org/js/telegram-web-app.js">`, an analytics tag, a CDN stylesheet, an embedded
    frame: each is a GET the browser sends when the page loads. A link to another site (`<a href="https://t.me/...">`,
    a component given one) is read too, as a LINK: the visitor follows it, the page does not fetch it. Read from HTML
    files and the markup of Svelte, Vue and JSX components; a relative URL is the site's own and is left out."""

    EXTENSIONS = ('.html', '.htm', '.svelte', '.vue', '.jsx', '.tsx')
    LINK = 'LINK'  # the method of a link a visitor follows
    ANCHOR = re.compile(
        r'<(?P<tag>a|[A-Z][\w.]*)\b[^>]*?\shref\s*=\s*["\'](?P<url>https?://[^"\'\s>]+)'
    )  # <a href="https://...">, or a component given one: <CtaButton href="https://...">
    TAG = re.compile(
        r'<(?P<tag>script|link|img|iframe|source|embed|video|audio)\b[^>]*?\s(?:src|href)\s*=\s*'
        r'["\'](?P<url>https?://[^"\'\s>]+)',
        re.I,
    )  # a tag that loads an absolute URL

    def __init__(self, files: RepositoryFiles):
        self._files = files
        self._policy = TestPathPolicy()

    def calls(self, repo: str) -> list[Call]:
        out = []
        for path in self._files.all_paths():
            if path.lower().endswith(self.EXTENSIONS):
                out += self._in(repo, path)
        return out

    def _in(self, repo, path):
        try:
            text = self._files.read(path).decode('utf-8', 'replace')
        except SourceReadError:
            return []
        test = self._policy.is_test(path)
        out = []
        for pattern, method in ((self.TAG, 'GET'), (self.ANCHOR, self.LINK)):
            for m in pattern.finditer(text):
                url = UrlTemplate.split(m.group('url'))
                if url.path is None:
                    continue
                line = text.count('\n', 0, m.start()) + 1
                hints = frozenset(url.hints) | {path, m.group('tag').lower()}
                out.append(Call(repo, path, line, PathTemplate.parse(url.path), method, '', hints, test=test))
        return out
