"""Next.js file-system routing: the URL path a file under `pages/api/` or `app/` serves."""

import re


class NextPath:
    """`pages/api/notes/[id].js` -> '/api/notes/{id}', `src/app/api/(shop)/orders/[...slug]/route.ts` ->
    '/api/orders/{*slug}'. The folder may sit under `src/` or in a package of a monorepo."""

    # a pages-router API file: everything under `pages/api/`, with the extension Next.js reads
    PAGES_API = re.compile(r'(?:^|/)pages/(api(?:/.*)?)\.(?:js|jsx|ts|tsx|mjs)$')
    # an app-router route handler: `app/<folders>/route.<ext>`
    APP_ROUTE = re.compile(r'(?:^|/)app/((?:[^/]+/)*)route\.(?:js|jsx|ts|tsx|mjs)$')
    CATCH_ALL = re.compile(r'^\[\[?\.\.\.(\w+)\]\]?$')  # '[...slug]' and the optional '[[...slug]]'
    DYNAMIC = re.compile(r'^\[(\w+)\]$')  # '[id]'
    INDEX = 'index'
    NOT_ROUTES = ('.d.ts', '.test.', '.spec.')

    @classmethod
    def pages_api(cls, path: str):
        """The path a pages-router API file serves, or None for any other file."""
        m = cls.PAGES_API.search(path)
        if m is None or any(n in path for n in cls.NOT_ROUTES):
            return None
        parts = m.group(1).split('/')
        if parts[-1] == cls.INDEX:
            parts = parts[:-1]
        return cls._join(parts)

    @classmethod
    def app_route(cls, path: str):
        """The path an app-router `route` file serves, or None for any other file."""
        m = cls.APP_ROUTE.search(path)
        if m is None or any(n in path for n in cls.NOT_ROUTES):
            return None
        parts = []
        for folder in m.group(1).split('/'):
            if folder.startswith('_'):
                return None  # a private folder: not routed
            if not (folder.startswith('(') and folder.endswith(')')) and not folder.startswith('@'):
                parts.append(folder)  # route groups '(shop)' and slots '@modal' are not in the URL
        return cls._join(parts)

    @classmethod
    def _join(cls, parts):
        out = []
        for part in (p for p in parts if p):
            if part.startswith('(') or part.startswith('_'):
                return None  # an intercepting route or a private file
            m = cls.CATCH_ALL.match(part) or cls.DYNAMIC.match(part)
            if m is None:
                out.append(part)
            else:
                out.append(('{*' if m.re is cls.CATCH_ALL else '{') + m.group(1) + '}')
        return '/' + '/'.join(out)
