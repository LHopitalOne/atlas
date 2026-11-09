import unittest

from atlas_bridge.core.addresses import Address, ServiceUrl
from atlas_bridge.core.http import Call, Extraction, PathTemplate, Route
from atlas_bridge.core.model import Status
from atlas_bridge.usecases.addresses import AddressBook
from atlas_bridge.usecases.link import LinkFinder, ServiceNames

P = PathTemplate.parse
REPOS = ['lms', 'discovery', 'credentials', 'web']


def url(name, value, repo='web'):
    return ServiceUrl.parse(repo, 'settings.py', 1, name, value)


class AddressTest(unittest.TestCase):
    def test_generic_hosts_name_no_service(self):
        for host in ('localhost', '127.0.0.1', '0.0.0.0', '10.0.0.5', '[::1]', 'host.docker.internal'):
            self.assertTrue(Address.is_generic(host), host)
        for host in ('edx.devstack.discovery', 'credentials', 'api.example.com'):
            self.assertFalse(Address.is_generic(host), host)

    def test_hints_with_a_port(self):
        self.assertEqual(Address.of_hint('localhost:18381'), ('localhost', '18381'))
        self.assertEqual(Address.of_hint('http://10.0.0.5:8000/api/v1'), ('10.0.0.5', '8000'))
        self.assertEqual(Address.of_hint('http://[::1]:8000/x'), ('[::1]', '8000'))
        self.assertIsNone(Address.of_hint('http://discovery/api'))  # no port
        self.assertIsNone(Address.of_hint('self.api_url'))

    def test_service_url(self):
        u = url('COURSE_CATALOG_API_URL', 'http://edx.devstack.discovery:18381/api/v1')
        self.assertEqual((u.host, u.port, str(u.path)), ('edx.devstack.discovery', '18381', '/api/v1'))
        self.assertEqual(u.address, 'edx.devstack.discovery:18381')
        self.assertFalse(u.generic_host)
        self.assertEqual(str(url('X', 'https://Example.COM').path), '/')
        self.assertEqual(url('X', 'https://example.com').address, '')
        self.assertIsNone(url('X', '/relative/path'))


class AddressBookTest(unittest.TestCase):
    def book(self, *urls, aliases=None):
        names = ServiceNames(REPOS, aliases)
        return AddressBook(list(urls), names.owner)

    def test_learns_addresses_hosts_names_and_prefixes(self):
        book = self.book(
            url('COURSE_CATALOG_API_URL', 'http://edx.devstack.discovery:18381/api/v1', repo='lms'),
            url('LMS_BASE_URL', 'http://localhost:18000'),
            url('CREDENTIALS_URL', 'http://10.1.2.3:18150'),
            aliases={'catalog': 'discovery'},
        )
        self.assertEqual(book.repos_for('localhost:18381'), set())  # only the docker name was configured
        self.assertEqual(book.repos_for('edx.devstack.discovery:18381'), {'discovery'})
        self.assertEqual(book.repos_for('edx.devstack.discovery:9999'), {'discovery'})  # by host
        self.assertEqual(book.repos_for('edx.devstack.discovery'), {'discovery'})
        self.assertEqual(book.repos_for('http://localhost:18000/api/x'), {'lms'})
        self.assertEqual(book.repos_for('localhost:9999'), set())  # localhost alone names nothing
        self.assertEqual(book.repos_for('10.1.2.3:18150'), {'credentials'})
        self.assertEqual(book.repos_for('settings.COURSE_CATALOG_API_URL'), {'discovery'})
        self.assertEqual(book.prefixes('discovery'), {'/api/v1'})
        self.assertEqual(book.prefixes('lms'), set())

    def test_a_name_counts_only_when_it_names_the_service(self):
        book = self.book(url('url', 'https://credentials.example.com/x'))
        self.assertEqual(book.repos_for('credentials.example.com'), {'credentials'})
        self.assertEqual(book.repos_for('url'), set())

    def test_an_address_two_services_claim_is_dropped(self):
        book = self.book(url('LMS_URL', 'http://localhost:8000'), url('DISCOVERY_URL', 'http://localhost:8000'))
        self.assertEqual(book.repos_for('localhost:8000'), set())
        self.assertEqual(book.repos_for('LMS_URL'), {'lms'})

    def test_urls_that_name_no_one_or_several_are_skipped(self):
        book = self.book(url('BASE_URL', 'http://localhost:2000'), url('LMS_DISCOVERY_URL', 'http://localhost:3000'))
        self.assertEqual(book.repos_for('localhost:2000') | book.repos_for('localhost:3000'), set())


class LinksByAddressTest(unittest.TestCase):
    ROUTES = [
        Route('discovery', 'urls.py', 1, P('/api/v1/course_runs/{pk}')),
        Route('discovery', 'urls.py', 2, P('/tagging/course_runs/{pk}')),
        Route('lms', 'urls.py', 3, P('/api/courses/v1/courses')),
    ]

    def links(self, *calls, urls=()):
        ex = Extraction(list(self.ROUTES), list(calls), list(urls))
        return [(lk.target, str(lk.route.path), lk.status) for lk in LinkFinder(REPOS).find(ex) if lk.route]

    def test_a_localhost_port_names_the_service(self):
        calls = [Call('web', 'a.py', 1, P('/api/courses/v1/courses'), 'GET', hints=frozenset({'localhost:18000'}))]
        self.assertEqual(self.links(*calls), [('lms', '/api/courses/v1/courses', Status.INFERRED)])  # path only
        found = self.links(*calls, urls=[url('LMS_ROOT_URL', 'http://localhost:18000')])
        self.assertEqual(found, [('lms', '/api/courses/v1/courses', Status.MATCHED)])

    def test_a_docker_name_and_the_prefix_it_carries(self):
        hints = frozenset({'edx.devstack.discovery:18381'})
        calls = [Call('web', 'a.py', 1, P('/course_runs/{id}'), 'GET', hints=hints)]
        found = self.links(*calls, urls=[url('DISCOVERY_API_URL', 'http://edx.devstack.discovery:18381/api/v1')])
        self.assertEqual(found, [('discovery', '/api/v1/course_runs/{pk}', Status.INFERRED)])


if __name__ == '__main__':
    unittest.main()
