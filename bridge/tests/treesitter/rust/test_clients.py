import unittest

from .support import RustRepo


class ClientTest(unittest.TestCase):
    def test_reqwest_verbs(self):
        found = RustRepo(
            """
static CLIENT: Lazy<Client> = Lazy::new(|| connection_from_url(settings.SNUBA_URL));

impl Symbolicator {
    async fn symbolicate(&self, id: u32, base: &str) {
        let url = format!("{}/symbolicate/{}", base, id);
        self.client.post(&url).send().await?;
        CLIENT.get("http://snuba:1218/health").send().await?;
        let client = reqwest::Client::builder().build().unwrap();
        client.delete(format!("{base_url}/items/{:?}?force=1", id)).send();
        self.http.put(format!("{0}/a/{{literal}}/{1}", base, id));
    }
}
"""
        ).calls()
        self.assertEqual(
            sorted(found),
            [('DELETE', '/items/{id}'), ('GET', '/health'), ('POST', '/symbolicate/{id}'), ('PUT', '/a/literal/{id}')],
        )
        post = found[('POST', '/symbolicate/{id}')]
        self.assertEqual((post.line, post.function, post.test), (7, 'Symbolicator::symbolicate', False))
        self.assertTrue({'base', 'self.client', 'Symbolicator', 'symbolicate', 'src/client.rs', 'send'} <= post.hints)
        health = found[('GET', '/health')]
        self.assertTrue({'snuba', 'CLIENT', 'Lazy::new(|| connection_from_url(settings.SNUBA_URL))'} <= health.hints)
        delete = found[('DELETE', '/items/{id}')]
        self.assertTrue({'base_url', 'reqwest::Client::builder().build().unwrap()'} <= delete.hints)

    def test_method_first_calls_and_join(self):
        found = RustRepo(
            """
fn send(client: &Client, base: Url, id: u64) {
    let req = Request::new(Method::POST, "/v1/upload");
    client.request(Method::PUT, base.join("files/").unwrap());
    let api = base.join("/api/0/").unwrap();
    let url = api.join(&format!("projects/{id}/events/")).unwrap();
    client.get(url.clone());
    ForwardRequest::builder(Method::POST, "/api/0/relays/register/").send_to(state.upstream_relay());
    reqwest::get("https://example.com/x/y");
    client.patch(BASE.to_string() + "/patch/" + &id.to_string());
    client.request(method, url);
}
"""
        ).calls()
        self.assertEqual(
            sorted(found),
            [
                ('ANY', '/api/0/projects/{id}/events'),
                ('GET', '/api/0/projects/{id}/events'),
                ('GET', '/x/y'),
                ('PATCH', '/patch/{id}'),
                ('POST', '/api/0/relays/register'),
                ('POST', '/v1/upload'),
                ('PUT', '/files'),
            ],
        )
        fwd = found[('POST', '/api/0/relays/register')]
        self.assertTrue({'ForwardRequest::builder', 'send_to', 'upstream_relay'} <= fwd.hints)
        self.assertIn('example.com', found[('GET', '/x/y')].hints)
        self.assertIn('BASE.to_string()', found[('PATCH', '/patch/{id}')].hints)

    def test_rejects_non_requests(self):
        found = RustRepo(
            """
fn f(request: &Request, map: &HashMap<String, String>) {
    request.headers().get("x-forwarded-for");
    map.get("key");
    cache.get(&key);
    client.get(url);
    client.get("  ");
    self.client.get(build_url());
    client.get(some.method("x"));
    other::post("/x");
    Self::get("/y");
    client.get("relative");
}
"""
        ).calls()
        self.assertEqual(sorted(found), [('GET', '/relative')])

    def test_join_and_concatenation_edges(self):
        found = RustRepo(
            """
const ROOT: &str = "http://svc/api/v1";
fn f(client: &Client, base: Url, id: u64) {
    let root = Url::parse(ROOT).unwrap();
    client.get(root.join("items").unwrap());
    client.post(base.join("rel").unwrap());
    client.put(base_url + "/things/" + id + "/x");
    client.delete(base.join(unknown()).unwrap());
    client.head(String::from("/head"));
    client.get(format!(no_literal));
    client.get(env!("X"));
    client.get(1 - 2);
}
"""
        ).calls()
        self.assertEqual(
            sorted(found), [('GET', '/api/items'), ('HEAD', '/head'), ('POST', '/rel'), ('PUT', '/things/{id}/x')]
        )
        self.assertIn('base_url', found[('PUT', '/things/{id}/x')].hints)
        self.assertIn('svc', found[('GET', '/api/items')].hints)

    def test_function_name_outside_functions(self):
        found = RustRepo('static R: Lazy<Response> = Lazy::new(|| client.get("/static"));\n').calls()
        self.assertEqual(found[('GET', '/static')].function, '')


if __name__ == '__main__':
    unittest.main()
