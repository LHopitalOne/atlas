"""Shared tree-sitter helpers: parsers per language, node text, string values as path templates, file listing."""

import functools
import os
import re
import subprocess

import tree_sitter as ts

EXTENSIONS = {
    '.py': 'python',
    '.rs': 'rust',
    '.js': 'javascript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'tsx',
}
SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', 'target', 'dist', 'build', '__pycache__', '.tox', 'vendor'}
TEST_DIRS = {
    'tests',
    'test',
    'testutils',
    'testing',
    'fixtures',
    '__tests__',
    '__mocks__',
    'e2e',
    'benches',
    'examples',
}
_TEST_FILE = re.compile(r'(^test_.*\.py$|_test\.py$|^conftest\.py$|\.(spec|test)\.[jt]sx?$|_test\.rs$)')
MAX_BYTES = 2_000_000  # generated or minified files are not worth parsing


@functools.cache
def language(name):
    if name == 'python':
        import tree_sitter_python as m

        return ts.Language(m.language())
    if name == 'rust':
        import tree_sitter_rust as m

        return ts.Language(m.language())
    if name == 'javascript':
        import tree_sitter_javascript as m

        return ts.Language(m.language())
    import tree_sitter_typescript as m

    return ts.Language(m.language_tsx() if name == 'tsx' else m.language_typescript())


def parse(name, source: bytes):
    return ts.Parser(language(name)).parse(source)


def text(node):
    return node.text.decode('utf-8', 'replace') if node is not None else ''


def line(node):
    return node.start_point[0] + 1


def walk(node, types=None):
    """Every node under `node` (depth first), or only those whose type is in `types`."""
    stack = [node]
    while stack:
        n = stack.pop()
        if types is None or n.type in types:
            yield n
        stack.extend(reversed(n.children))


def ancestor(node, types):
    n = node.parent
    while n is not None and n.type not in types:
        n = n.parent
    return n


def placeholder(expr: str):
    """A readable parameter name for an interpolated expression: 'request.dataset' -> 'dataset'."""
    words = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', expr)
    return words[-1] if words else 'param'


def string_value(node):
    """The value of a string literal as a template: interpolations become {name}. None if not a string."""
    t = node.type
    if t == 'concatenated_string':  # python "a" "b"
        parts = [string_value(c) for c in node.named_children]
        return None if None in parts else ''.join(parts)
    if t in ('string', 'template_string', 'string_literal', 'raw_string_literal'):
        out = []
        for c in node.children:
            if c.type in ('string_content', 'string_fragment', 'escape_sequence'):
                out.append(text(c))
            elif c.type in ('interpolation', 'template_substitution'):
                inner = [x for x in c.named_children if x.type not in ('format_specifier', 'type_conversion')]
                out.append('{' + placeholder(text(inner[0]) if inner else '') + '}')
        if t == 'raw_string_literal' and not out:
            raw = text(node)
            return raw[raw.find('"') + 1 : raw.rfind('"')]
        return ''.join(out)
    return None


_BASE = re.compile(r'url|uri|base|host|server|endpoint|addr|prefix|upstream|origin|root', re.I)


def split_url(value: str):
    """Separate a URL template into (path, base hints).

    'http://api:8000/orders' -> ('/orders', ['api']); '{BASE}/orders/{id}' -> ('/orders/{id}', ['BASE']);
    '{}/x' (a positional format base) -> ('/x', []); 'symbolicate' -> ('/symbolicate', []).
    Returns (None, []) for values that are clearly not request paths (blank, whitespace, plain words with spaces).
    """
    v = value.strip()
    if not v or ' ' in v or '\n' in v:
        return None, []
    hints = []
    m = re.match(r'^[a-z][a-z0-9+.-]*://([^/]*)', v, re.I)
    if m:
        hints.append(m.group(1).split(':')[0])
        v = v[m.end() :] or '/'
    else:
        m = re.match(r'^\{([^{}]*)\}(?=/|$)', v)
        if m and (not m.group(1) or _BASE.search(m.group(1)) or m.group(1).isupper()):
            if m.group(1):
                hints.append(m.group(1))
            v = v[m.end() :] or '/'
    if not v.startswith('/'):
        v = '/' + v
    return v.split('?')[0].split('#')[0], hints


def is_test_path(path):
    parts = path.replace('\\', '/').split('/')
    return any(p in TEST_DIRS for p in parts[:-1]) or bool(_TEST_FILE.search(parts[-1]))


def list_files(root):
    """Source files under root, relative paths. Uses git when root is a repository (honours .gitignore)."""
    try:
        out = subprocess.run(['git', 'ls-files', '-z'], cwd=root, capture_output=True, check=True).stdout
        paths = [p for p in out.decode('utf-8', 'replace').split('\0') if p]
    except (OSError, subprocess.CalledProcessError):
        paths = []
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            paths += [os.path.relpath(os.path.join(d, f), root) for f in files]
    return sorted(p for p in paths if os.path.splitext(p)[1] in EXTENSIONS)


def read(root, path):
    full = os.path.join(root, path)
    try:
        if os.path.getsize(full) > MAX_BYTES:
            return None
        with open(full, 'rb') as f:
            return f.read()
    except OSError:
        return None
