"""Service URLs in configuration files: `.env` variables and docker-compose services."""

import re

from ....core.addresses import ServiceUrl
from ....core.errors import SourceReadError


class EnvFile:
    """`NAME=http://host:port/path` lines (quotes and `export` allowed) in `.env`, `.env.development`..."""

    LINE = re.compile(
        r'^\s*(?:export\s+)?(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<quote>[\'"]?)(?P<value>[^\'"#\s]*)(?P=quote)'
    )  # NAME=value, NAME='value', export NAME="value"

    @classmethod
    def urls(cls, repo, path, text):
        out = []
        for i, line in enumerate(text.splitlines(), 1):
            m = cls.LINE.match(line)
            url = ServiceUrl.parse(repo, path, i, m.group('name'), m.group('value')) if m else None
            if url is not None:
                out.append(url)
        return out


class ComposeFile:
    """The services of a docker-compose file: each is reachable inside the network at its name, `container_name`
    and `hostname` on the container port, and from the host at `localhost` on each published port."""

    SERVICES = 'services'
    KEY = re.compile(r'^(?P<indent> *)(?P<key>[\w.-]+):\s*(?P<value>.*?)\s*$')
    ITEM = re.compile(r'^\s*-\s*[\'"]?(?P<value>[^\'"#]+?)[\'"]?\s*$')
    PORTS = re.compile(r'^(?:[\d.]+:(?=\d+:\d))?(?:(?P<host>\d+):)?(?P<container>\d+)(?:/\w+)?$')  # '[ip:]8080:80'
    NAMES = ('container_name', 'hostname')

    @classmethod
    def urls(cls, repo, path, text):
        out = []
        for name, line, keys, ports in cls._services(text.splitlines()):
            hosts = [name] + [keys[k] for k in cls.NAMES if keys.get(k)]
            for host_port, container_port in ports:
                out += [ServiceUrl(repo, path, line, name, h.lower(), container_port) for h in hosts]
                if host_port:
                    out.append(ServiceUrl(repo, path, line, name, 'localhost', host_port))
        return out

    @classmethod
    def _services(cls, lines):
        """(name, line, {key: value}, [(host port, container port)]) per service."""
        services, current, indent, in_ports, inside = [], None, None, False, False
        for i, line in enumerate(lines, 1):
            m = cls.KEY.match(line)
            item = cls.ITEM.match(line)
            if m and not m.group('indent'):
                inside, current = m.group('key') == cls.SERVICES, None
            elif inside and m and (indent is None or len(m.group('indent')) == indent):
                indent = len(m.group('indent'))
                current = (m.group('key'), i, {}, [])
                services.append(current)
                in_ports = False
            elif current is not None and m:
                in_ports = m.group('key') == 'ports'
                current[2][m.group('key')] = m.group('value').strip('\'"')
            elif current is not None and in_ports and item:
                ports = cls.PORTS.match(item.group('value').strip())
                if ports:
                    current[3].append((ports.group('host') or '', ports.group('container')))
        return services


class ConfigFiles:
    """The configuration files of a repository that name service URLs, read with the matching reader."""

    ENV = re.compile(r'(^|/)\.env(\.[\w-]+)?$')
    COMPOSE = re.compile(r'(^|/)(docker-)?compose[\w.-]*\.ya?ml$')
    TEST_ENV = re.compile(r'\.env\.test')

    def __init__(self, files):
        self._files = files  # RepositoryFiles

    def urls(self, repo):
        out = []
        for path in self._files.all_paths():
            reader = self._reader(path)
            if reader is None:
                continue
            try:
                text = self._files.read(path).decode('utf-8', 'replace')
            except SourceReadError:
                continue
            out += reader.urls(repo, path, text)
        return out

    @classmethod
    def _reader(cls, path):
        if cls.ENV.search(path) and not cls.TEST_ENV.search(path):
            return EnvFile
        return ComposeFile if cls.COMPOSE.search(path) else None
