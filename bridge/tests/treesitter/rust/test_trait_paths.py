import unittest

from .support import RustRepo

REQUESTS = """
use std::borrow::Cow;

impl UpstreamQuery for GetProjectStates {
    type Response = Resp;

    fn method(&self) -> Method {
        Method::POST
    }

    fn path(&self) -> Cow<'static, str> {
        Cow::Borrowed("/api/0/relays/projectconfigs/?version=3")
    }
}

impl UpstreamRequest for SendEnvelope {
    fn method(&self) -> reqwest::Method {
        reqwest::Method::POST
    }

    fn path(&self) -> Cow<'_, str> {
        format!("/api/{}/envelope/", self.envelope.scoping().project_id).into()
    }
}

impl UpstreamRequest for GetHealthCheck {
    fn method(&self) -> Method { Method::GET }
    fn path(&self) -> Cow<'_, str> { "/api/0/relays/live/".into() }
}

impl UpstreamRequest for UploadRequest {
    fn method(&self) -> Method {
        match self.kind {
            Kind::Create { .. } => Method::POST,
            Kind::Upload { .. } => Method::PATCH,
        }
    }

    fn path(&self) -> Cow<'_, str> {
        let project_id = self.project_id;
        match &self.kind {
            Kind::Create { id, .. } => Cow::Owned(format!("/api/{project_id}/upload/")),
            Kind::Upload { uri } => Cow::Borrowed(uri),
        }
    }
}

impl Endpoint for Thing<T> {
    fn url(&self) -> String {
        String::from(THING_PATH)
    }
}

impl Display for Other {
    fn fmt(&self) -> String { "/not/a/request".into() }
}

const THING_PATH: &str = "/things/";

#[cfg(test)]
mod tests {
    impl UpstreamRequest for Fake {
        fn path(&self) -> Cow<'_, str> { "/fake/".into() }
    }
}
"""


class RequestTraitTest(unittest.TestCase):
    def setUp(self):
        self.found = RustRepo({'src/services/upstream.rs': REQUESTS}).calls()

    def test_paths_and_methods(self):
        self.assertEqual(
            sorted(self.found),
            [
                ('ANY', '/fake'),
                ('ANY', '/things'),
                ('GET', '/api/0/relays/live'),
                ('POST', '/api/0/relays/projectconfigs'),
                ('POST', '/api/{project_id}/envelope'),
                ('POST', '/api/{project_id}/upload'),  # the method of the matching arm of `fn method`
            ],
        )
        c = self.found[('POST', '/api/0/relays/projectconfigs')]
        self.assertEqual((c.line, c.function, c.test), (12, 'GetProjectStates::path', False))
        self.assertTrue({'UpstreamQuery', 'Upstream Query', 'GetProjectStates', 'src/services/upstream.rs'} <= c.hints)
        self.assertEqual(self.found[('ANY', '/things')].function, 'Thing::url')
        self.assertTrue(self.found[('ANY', '/fake')].test)

    def test_nested_generics_stripped(self):
        found = RustRepo(
            'impl UpstreamRequest<Vec<u8>> for Foo<Option<T>> {\n'
            '    fn method(&self) -> Method { Method::POST }\n'
            '    fn path(&self) -> Cow<str> { "/api/x/".into() }\n'
            '}\n'
        ).calls()
        c = found[('POST', '/api/x')]
        self.assertEqual(c.function, 'Foo::path')
        self.assertTrue({'Foo', 'UpstreamRequest'} <= c.hints)

    def test_ambiguous_method_and_blank_paths(self):
        found = RustRepo(
            'impl UpstreamRequest for Either {\n'
            '    fn method(&self) -> Method { if a { Method::GET } else { Method::PUT } }\n'
            '    fn endpoint(&self) -> String { "/either".into() }\n'
            '    fn url(&self) -> String { " ".into() }\n'
            '}\n'
            'impl Inherent { fn path(&self) -> &str { "/inherent" } }\n'
        ).calls()
        self.assertEqual(sorted(found), [('ANY', '/either')])
        self.assertEqual(found[('ANY', '/either')].function, 'Either::endpoint')


if __name__ == '__main__':
    unittest.main()
