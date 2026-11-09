import os
import tempfile
import textwrap
import unittest

from atlas_bridge.adapters.treesitter.kit import ComposeFile, ConfigFiles, EnvFile, RepositoryFiles

COMPOSE = """
version: "3"
services:
  discovery:
    container_name: edx.devstack.discovery
    build: .
    ports:
      - "18381:18381"
      - 9000
    environment:
      - DJANGO_SETTINGS_MODULE=x
  db:
    image: mysql
volumes:
  data: {}
"""


def summary(urls):
    return sorted((u.name, u.host, u.port, str(u.path)) for u in urls)


class EnvFileTest(unittest.TestCase):
    def test_urls(self):
        text = textwrap.dedent("""
            LMS_BASE_URL='http://localhost:18000'
            export DISCOVERY_API_BASE_URL="http://10.0.0.5:18381/api/v1"  # comment
            SITE_NAME=localhost
            EMPTY=
        """)
        self.assertEqual(
            summary(EnvFile.urls('web', '.env', text)),
            [('DISCOVERY_API_BASE_URL', '10.0.0.5', '18381', '/api/v1'), ('LMS_BASE_URL', 'localhost', '18000', '/')],
        )


class ComposeFileTest(unittest.TestCase):
    def test_services_names_and_ports(self):
        self.assertEqual(
            summary(ComposeFile.urls('discovery', 'docker-compose.yml', COMPOSE)),
            [
                ('discovery', 'discovery', '18381', '/'),
                ('discovery', 'discovery', '9000', '/'),
                ('discovery', 'edx.devstack.discovery', '18381', '/'),
                ('discovery', 'edx.devstack.discovery', '9000', '/'),
                ('discovery', 'localhost', '18381', '/'),
            ],
        )


class ConfigFilesTest(unittest.TestCase):
    def test_reads_env_and_compose_files_but_not_test_env(self):
        files = {
            '.env.development': "LMS_BASE_URL='http://localhost:18000'\n",
            '.env.test': "LMS_BASE_URL='http://localhost:9999'\n",
            'docker-compose.yml': COMPOSE,
            'deploy/compose.prod.yaml': 'services:\n  web:\n    ports:\n      - "80:8000"\n',
            'README.md': 'LMS_BASE_URL=http://localhost:1\n',
        }
        with tempfile.TemporaryDirectory() as root:
            for path, text in files.items():
                full = os.path.join(root, path)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, 'w') as f:
                    f.write(text)
            os.mkdir(os.path.join(root, '.env.dir'))  # a folder named like an env file is not read
            urls = ConfigFiles(RepositoryFiles(root)).urls('web')
        self.assertEqual(
            sorted({(u.file, u.name, u.address) for u in urls}),
            [
                ('.env.development', 'LMS_BASE_URL', 'localhost:18000'),
                ('deploy/compose.prod.yaml', 'web', 'localhost:80'),
                ('deploy/compose.prod.yaml', 'web', 'web:8000'),
                ('docker-compose.yml', 'discovery', 'discovery:18381'),
                ('docker-compose.yml', 'discovery', 'discovery:9000'),
                ('docker-compose.yml', 'discovery', 'edx.devstack.discovery:18381'),
                ('docker-compose.yml', 'discovery', 'edx.devstack.discovery:9000'),
                ('docker-compose.yml', 'discovery', 'localhost:18381'),
            ],
        )


if __name__ == '__main__':
    unittest.main()
