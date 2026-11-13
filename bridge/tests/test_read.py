"""Requests the extractors miss, found by a reader (usecases/read.py), every claim checked against the code
(usecases/reading.py), and what the model is shown and how its answer is read (adapters/muse/requests.py). The reader
here is a stand-in: no request leaves the machine."""

import json
import os
import unittest
import unittest.mock

from atlas_bridge.adapters.atlas.records import LinkRecord
from atlas_bridge.adapters.muse import MuseReader, RequestPrompt
from atlas_bridge.core.errors import JudgeUnavailableError
from atlas_bridge.core.evidence import Verification
from atlas_bridge.core.http import Call, Extraction, PathTemplate, Route
from atlas_bridge.core.model import Status
from atlas_bridge.usecases.channels import OwnChannelRule
from atlas_bridge.usecases.link import Link, LinkFinder
from atlas_bridge.usecases.outside import OutsideRule
from atlas_bridge.usecases.ports import (
    FileReading,
    ReadCase,
    ReadHelper,
    ReadRequest,
    ReadRoute,
    RequestReader,
    SourceFiles,
)
from atlas_bridge.usecases.read import ReadFinders, ReadLinks
from atlas_bridge.usecases.reading import ReadCheck, ReadUrl
from atlas_bridge.usecases.within import ReadWithinRule, WithinRepoRule

P = PathTemplate.parse
HEALTH = Route('collector', 'api.py', 3, P('/healthz'), frozenset({'GET'}), 'health')
ITEMS = Route('collector', 'api.py', 9, P('/api/items/{id}'), frozenset({'GET'}), 'item')
METRICS = """import { http } from "./http.js";

export async function health() {
  const res = await http.get("/healthz");
  return res.data;
}
"""
CLIENT = """import axios from "axios";
export const http = axios.create({ baseURL: config.collectorUrl });
"""


class Files(SourceFiles):
    def __init__(self, files):
        self.files = files  # {(repo, path): text}

    def paths(self, repo):
        return sorted(p for r, p in self.files if r == repo)

    def text(self, repo, path):
        return self.files.get((repo, path), '')


class Script(RequestReader):
    """Answers each file with what `answers` holds for it (a function of the case); records what it was asked."""

    model = 'test/model'

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def read(self, cases):
        self.asked += cases
        return [self.answers.get(c.path, lambda c: None)(c) for c in cases]


def health_request(case):
    url = '{config.collectorUrl}/healthz' if case.helpers else '/healthz'
    return FileReading((ReadRequest(4, 'const res = await http.get("/healthz");', 'GET', url, 'http', through='http'),))


def finders(repos=('dashboard', 'collector')):
    rules = (*LinkFinder.RULES[:-1], OwnChannelRule, LinkFinder.RULES[-1])
    return ReadFinders(
        LinkFinder(list(repos), rules=rules), LinkFinder(list(repos), rules=rules, fallbacks=(OutsideRule,))
    )


def refine(files, answers, links=(), routes=(HEALTH, ITEMS), calls=(), repos=('dashboard', 'collector')):
    reader = Script(answers)
    read = ReadLinks(reader, Files(files), finders(repos), list(repos))
    return read.refine(list(links), Extraction(list(routes), list(calls))), read, reader


class ReadUrlTest(unittest.TestCase):
    def test_absolute_based_relative_and_channel(self):
        url = ReadUrl('https://API.x.com:443/v1/items?q=1', 'http')
        self.assertEqual((url.host, url.path), ('api.x.com', '/v1/items?q=1'))
        url = ReadUrl('${settings.api}/users/${id}', 'http')
        self.assertEqual((url.base, url.path), ('settings.api', '/users/{id}'))
        self.assertEqual(ReadUrl('orders.created', 'kafka').path, '/orders.created')
        self.assertEqual(ReadUrl('users/1', 'http').path, '')  # a relative HTTP path says too little
        url = ReadUrl("${config.get('apiHost')}${config.get('apiPath')}${version}/addons/{slug}/", 'http')
        self.assertEqual((url.base, url.path), ("config.get('apiHost')", '/addons/{slug}/'))
        self.assertEqual(url.bases, ("config.get('apiHost')", "config.get('apiPath')", 'version'))


class ReadCheckTest(unittest.TestCase):
    CASE = ReadCase('dashboard', 'src/metrics.ts', METRICS)

    def check(self, line=4, code='await http.get("/healthz")', url='/healthz', **kw):
        return ReadCheck().call(self.CASE, ReadRequest(line, code, 'GET', url, kw.pop('protocol', 'http'), **kw))

    def test_a_claim_the_code_bears_out_is_a_call_on_the_line_the_code_is(self):
        call = self.check(line=6, function='health', base='{config.collectorUrl}')
        self.assertEqual((call.line, str(call.path), call.method, call.function), (4, '/healthz', 'GET', 'health'))
        self.assertEqual(call.hints, frozenset())  # the base is not written in this file

    def test_invented_words_lines_and_hosts_are_dropped(self):
        self.assertIsNone(self.check(url='/api/accounts'))  # 'accounts' is not in the file
        self.assertIsNone(self.check(code='requests.post(url)'))  # no such line
        self.assertIsNone(self.check(url='https://evil.example.com/healthz'))  # a host the file does not write
        self.assertIsNone(self.check(protocol='carrier-pigeon'))
        self.assertIsNone(self.check(code='http'))  # too short to place

    def test_a_quote_with_words_of_the_readers_own_is_placed_nearby(self):
        call = self.check(line=5, code='const res = await http.get("/healthz") in health()')
        self.assertEqual(call.line, 4)

    def test_the_helper_a_request_goes_through_vouches_for_its_words(self):
        helper = ReadHelper('http', '', '{config.collectorUrl}', ReadHelper.CLIENT)
        case = ReadCase('dashboard', 'src/metrics.ts', METRICS, (helper,))
        call = ReadCheck().call(
            case,
            ReadRequest(4, 'http.get("/healthz")', 'GET', '{config.collectorUrl}/healthz', 'http', through='http.get'),
        )
        self.assertEqual(call.hints, frozenset({'config.collectorUrl'}))

    def test_helpers_worth_telling_other_files_about(self):
        check, case = ReadCheck(), ReadCase('dashboard', 'src/http.ts', CLIENT)
        self.assertTrue(check.helper_ok(case, ReadHelper('http', '', '{config.collectorUrl}', ReadHelper.CLIENT)))
        self.assertFalse(check.helper_ok(case, ReadHelper('http', '', '{config.otherUrl}', ReadHelper.CLIENT)))
        self.assertFalse(check.helper_ok(case, ReadHelper('send', 'POST', '/api/{path}')))  # 'send' is not here

    def test_a_wrapper_its_callers_pass_the_path_to_is_a_helper_when_its_base_is_written(self):
        check, case = ReadCheck(), ReadCase('web', 'src/api.js', WRAPPER)
        self.assertTrue(check.helper_ok(case, ReadHelper('callApi', '', '{COLLECTOR_URL}{API_PATH}/{endpoint}/')))
        self.assertFalse(check.helper_ok(case, ReadHelper('callApi', '', '{OTHER_HOST}/{endpoint}/')))
        self.assertFalse(check.helper_ok(case, ReadHelper('callApi', '', '{endpoint}')))  # no base at all


WRAPPER = """export function callApi({ endpoint, method = 'GET' }) {
  return fetch(`${COLLECTOR_URL}${API_PATH}/${endpoint}/`, { method });
}
"""
SEARCH = """import { callApi } from './api';

export const search = (q) => callApi({ endpoint: 'items/search', params: { q } });
"""
SEARCH_ROUTE = Route('collector', 'urls.py', 4, P('/api/v1/items/search'), frozenset({'GET'}), 'search')


class ReadLinksTest(unittest.TestCase):
    FILES = {('dashboard', 'src/metrics.ts'): METRICS, ('dashboard', 'src/http.ts'): CLIENT}

    def test_a_client_helper_lets_the_second_reading_name_the_service(self):
        answers = {
            'src/metrics.ts': health_request,
            'src/http.ts': lambda c: FileReading(helpers=(ReadHelper('http', '', '{config.collectorUrl}', 'client'),)),
        }
        out, read, reader = refine(self.FILES, answers)
        (link,) = out
        self.assertEqual((link.target, link.route, link.status), ('collector', HEALTH, Status.INFERRED))
        self.assertEqual(link.verification, Verification.READ)
        self.assertIn('test/model read the request', link.reason)
        self.assertEqual([c.path for c in reader.asked], ['src/http.ts', 'src/metrics.ts', 'src/metrics.ts'])
        self.assertEqual((read.report.files, read.report.again, read.report.linked), (2, 1, 1))

    def test_without_the_helper_a_one_word_path_names_no_service(self):
        out, read, _ = refine(self.FILES, {'src/metrics.ts': health_request})
        self.assertEqual(out, [])
        self.assertEqual((read.report.claimed, read.report.checked, read.report.linked), (1, 1, 0))

    def test_files_with_every_request_linked_are_not_read_and_open_links_give_way(self):
        call = Call('dashboard', 'src/metrics.ts', 4, P('/healthz'), 'GET', hints=frozenset({'config.collectorUrl'}))
        settled = Link(call, 'dashboard', 'collector', HEALTH, Status.MATCHED, 'named target')
        out, _, reader = refine({('dashboard', 'src/metrics.ts'): METRICS}, {}, [settled])
        self.assertEqual((out, reader.asked), ([settled], []))
        open_ = Link(call, 'dashboard', 'collector', None, Status.UNMATCHED, 'no route fits')
        answers = {
            'src/metrics.ts': health_request,
            'src/http.ts': lambda c: FileReading(helpers=(ReadHelper('http', '', '{config.collectorUrl}', 'client'),)),
        }
        out, _, _ = refine(self.FILES, answers, [open_])
        self.assertEqual([(lk.status, lk.verification) for lk in out], [(Status.INFERRED, Verification.READ)])

    def test_files_that_pass_a_wrapper_the_path_are_read_again_with_it(self):
        url = '{COLLECTOR_URL}{API_PATH}/{endpoint}/'
        quote = "callApi({ endpoint: 'items/search', params: { q } })"
        answers = {
            'src/api.js': lambda c: FileReading(helpers=(ReadHelper('callApi', 'GET', url),)),
            'src/search.js': lambda c: (
                FileReading(
                    (
                        ReadRequest(
                            3, quote, 'GET', '{COLLECTOR_URL}{API_PATH}/items/search/', 'http', through='callApi'
                        ),
                    )
                )
                if c.helpers
                else None
            ),
        }
        files = {('dashboard', 'src/api.js'): WRAPPER, ('dashboard', 'src/search.js'): SEARCH}
        out, _, reader = refine(files, answers, routes=(SEARCH_ROUTE,))
        self.assertEqual([c.path for c in reader.asked], ['src/api.js', 'src/search.js'])
        (link,) = out
        self.assertEqual((link.call.file, link.call.line, link.route), ('src/search.js', 3, SEARCH_ROUTE))
        self.assertEqual(link.call.hints, frozenset({'COLLECTOR_URL', 'API_PATH'}))

    def test_a_function_whose_request_settled_is_no_helper(self):
        caller = 'import { health } from "./metrics";\nexport const ok = () => health();\n'
        files = {**self.FILES, ('dashboard', 'src/index.ts'): caller}
        call = Call('dashboard', 'src/metrics.ts', 4, P('/healthz'), 'GET', 'health', frozenset({'collector'}))
        settled = Link(call, 'dashboard', 'collector', HEALTH, Status.MATCHED, 'named target')
        answers = {'src/metrics.ts': lambda c: FileReading(helpers=(ReadHelper('health', 'GET', '/healthz'),))}
        _, _, reader = refine(files, answers, [settled])
        self.assertNotIn('src/index.ts', [c.path for c in reader.asked])


JOBS = """export class MailService {
  async send(to) {
    await this.jobRepository.queue({ name: JobName.SendMail, data: { to } });
  }

  @OnJob({ name: JobName.SendMail, queue: QueueName.Notification })
  async handleSendMail(job) {}
}
"""


class ReadRoutesTest(unittest.TestCase):
    def test_a_job_read_on_both_sides_links_by_the_constant_they_share(self):
        def answer(case):
            send = ReadRequest(
                3, 'await this.jobRepository.queue({ name: JobName.SendMail', '', 'JobName.SendMail', 'task'
            )
            serve = ReadRoute(6, '@OnJob({ name: JobName.SendMail', '', '{JobName.SendMail}', 'task', 'handleSendMail')
            return FileReading((send,), (), (serve,))

        out, read, _ = refine({('server', 'src/mail.ts'): JOBS}, {'src/mail.ts': answer}, routes=(), repos=('server',))
        (link,) = out
        self.assertEqual((link.call.line, link.route.line, str(link.route.path)), (3, 6, '/sendmail'))
        self.assertEqual(
            (link.route.handler, link.route.framework, link.verification), ('handleSendMail', 'read', Verification.READ)
        )
        self.assertEqual(read.report.routes, 1)

    def test_a_request_the_extractors_left_open_meets_a_route_read(self):
        call = Call('server', 'src/mail.ts', 3, P('/SendMail'), protocol='task')
        serve = ReadRoute(6, '@OnJob({ name: JobName.SendMail', '', 'JobName.SendMail', 'task', 'handleSendMail')
        answers = {'src/mail.ts': lambda c: FileReading(routes=(serve,))}
        out, _, _ = refine({('server', 'src/mail.ts'): JOBS}, answers, routes=(), calls=(call,), repos=('server',))
        self.assertEqual([(lk.call, lk.route.line, lk.verification) for lk in out], [(call, 6, Verification.READ)])

    def test_a_relay_that_takes_every_event_serves_none_of_them(self):
        code = (
            "const EVENTS = ['HlsSessionResult'];\n"
            + '\n' * 4
            + 'for (const event of EVENTS) {\n  server.on(event, relay);\n}\n'
        )
        claim = ReadRoute(7, 'server.on(event, relay);', '', 'HlsSessionResult', 'websocket')
        self.assertIsNone(ReadCheck().route(ReadCase('server', 'src/ws.ts', code), claim))

    def test_links_a_person_clicks_and_redirects_are_not_requests(self):
        code = '\n'.join(
            [
                '<Hyperlink destination={`${lms}/register`}>',
                'return redirect(f"{mfe}/courses")',
                'location.href = `${lms}/register`;',
            ]
        )
        check, case = ReadCheck(), ReadCase('web', 'src/a.jsx', code)
        clicked = ReadRequest(1, '<Hyperlink destination={`${lms}/register`}>', 'GET', '{lms}/register', 'http')
        redirected = ReadRequest(2, 'return redirect(f"{mfe}/courses")', 'GET', '{mfe}/courses', 'http')
        navigated = ReadRequest(3, 'location.href = `${lms}/register`;', 'GET', '{lms}/register', 'http')
        self.assertEqual([check.call(case, r) is None for r in (clicked, redirected, navigated)], [True, True, False])

    def test_a_channel_held_in_a_variable_is_no_channel(self):
        code = "const queueName = pick(job);\nawait this.queues[queueName].add(job);\nemit('ready');\n"
        check, case = ReadCheck(), ReadCase('server', 'src/q.ts', code)
        self.assertIsNone(
            check.call(case, ReadRequest(2, 'await this.queues[queueName].add(job);', '', 'queueName', 'task'))
        )
        self.assertIsNotNone(check.call(case, ReadRequest(3, "emit('ready');", '', 'ready', 'websocket')))

    def test_routes_the_code_does_not_bear_out_or_the_extractors_read_are_left_out(self):
        check, case = ReadCheck(), ReadCase('server', 'src/mail.ts', JOBS)
        self.assertIsNone(
            check.route(case, ReadRoute(6, '@OnJob({ name: JobName.SendMail', '', 'JobName.Refund', 'task'))
        )
        self.assertIsNone(check.route(case, ReadRoute(6, '@Get("/nothing")', 'GET', '/users', 'http')))
        self.assertIsNone(
            check.route(
                ReadCase('api', 'v.py', 'def courses(self):\n'),
                ReadRoute(1, 'def courses(self):', 'GET', '/courses', 'http'),
            )
        )
        django = ReadCase('api', 'urls.py', "urlpatterns = [path('api/items/<int:pk>/', item_view)]\n")
        route = check.route(
            django,
            ReadRoute(
                1, "path('api/items/<int:pk>/', item_view)", 'GET, POST', 'api/items/<int:pk>/', 'http', 'item_view'
            ),
        )
        self.assertEqual((str(route.path), route.methods), ('/api/items/{pk}', frozenset({'GET', 'POST'})))


class ReadWithinRuleTest(unittest.TestCase):
    def test_a_read_request_from_a_server_file_may_reach_its_own_routes(self):
        call = Call('zulip', 'zerver/tornado.py', 3, P('/api/v1/events/internal'), 'POST')
        route = Route('zulip', 'zproject/urls.py', 9, P('/api/v1/events/internal'), frozenset({'POST'}))
        own = LinkFinder(['zulip'], rules=(WithinRepoRule,)).find(Extraction([route], [call]))
        read = LinkFinder(['zulip'], rules=(ReadWithinRule,)).find(Extraction([route], [call]))
        self.assertEqual((own, [lk.route for lk in read]), ([], [route]))


class RequestPromptTest(unittest.TestCase):
    def test_the_file_is_numbered_and_the_helpers_listed(self):
        helper = ReadHelper('http', '', '{config.collectorUrl}', ReadHelper.CLIENT)
        messages = RequestPrompt().messages(ReadCase('dashboard', 'src/metrics.ts', METRICS, (helper,)))
        self.assertIn('4|   const res = await http.get("/healthz");', messages[1]['content'])
        self.assertIn('http is a client whose base URL is {config.collectorUrl}', messages[1]['content'])
        self.assertIsNone(RequestPrompt().messages(ReadCase('d', 'empty.ts', '  \n')))

    def test_the_answer_is_read_and_broken_items_left_out(self):
        answer = {
            'requests': [
                {'line': '4', 'code': 'http.get("/healthz")', 'method': 'GET', 'url': '/healthz', 'protocol': 'http'},
                {'line': 'x', 'code': 'a', 'url': '/a'},
                {'line': 2, 'code': '', 'url': '/b'},
            ],
            'helpers': [{'function': 'http', 'kind': 'client', 'method': '', 'url': '{base}'}, {'function': ''}],
        }
        reading = RequestPrompt.reading(json.dumps(answer))
        self.assertEqual([(r.line, r.url) for r in reading.requests], [(4, '/healthz')])
        self.assertEqual([(h.function, h.kind) for h in reading.helpers], [('http', 'client')])
        self.assertIsNone(RequestPrompt.reading('not json'))

    def test_no_key_is_a_clear_error(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(JudgeUnavailableError):
            MuseReader()


class ReadProofTest(unittest.TestCase):
    def test_a_read_link_shows_as_read_unless_it_leaves_the_repositories(self):
        record = LinkRecord.__new__(LinkRecord)
        for status, proof in (('inferred', 'read'), ('outside', 'outside')):
            object.__setattr__(record, 'status', status)
            object.__setattr__(record, 'verification', 'read')
            self.assertEqual(record.proof, proof)


if __name__ == '__main__':
    unittest.main()
