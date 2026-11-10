import unittest

from atlas_bridge.core.http import ANY

from .support import RustRepo

TINY = """
use tiny_http::{Method, Request, Response};

fn handle(request: Request) {
    let response = match (request.method(), request.url()) {
        (Method::Get, "/stock") => Response::from_string("[]"),
        (Method::Post, "/stock/reserve") => Response::from_string("{}"),
        (_, "/ping") => Response::from_string("pong"),
        (Method::Get, path) => Response::from_string(path),
        _ => Response::from_string("not found"),
    };
    let _ = request.respond(response);
}

fn not_a_request(pair: (u8, &str)) {
    match (pair.method(), pair.url()) {
        (Method::Get, "/nope") => {}
        _ => {}
    }
}
"""
HYPER = """
use hyper::{Method, Request};

async fn route(req: Request<Body>) -> Response<Body> {
    match (req.method(), req.uri().path()) {
        (&Method::GET, "/health") => ok(),
        _ => not_found(),
    }
}
"""


class MatchRoutesTest(unittest.TestCase):
    def test_arms_of_a_match_on_a_requests_method_and_path(self):
        routes = RustRepo({'src/http.rs': TINY, 'src/hyper.rs': HYPER}).routes()
        self.assertEqual(
            set(routes), {('GET', '/stock'), ('POST', '/stock/reserve'), (ANY, '/ping'), ('GET', '/health')}
        )
        self.assertEqual(routes['GET', '/stock'].handler, 'handle')


if __name__ == '__main__':
    unittest.main()
