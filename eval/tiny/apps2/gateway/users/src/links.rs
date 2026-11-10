//! Access log: one `RECV <link id>` line per request that arrives over a known link.

use axum::extract::{MatchedPath, Request};
use axum::http::Method;
use axum::middleware::Next;
use axum::response::Response;

pub async fn log_received(req: Request, next: Next) -> Response {
    let via_gateway = req.headers().contains_key("x-forwarded-for");
    if let Some(route) = req.extensions().get::<MatchedPath>() {
        if let Some(id) = link_id(req.method(), route.as_str(), via_gateway) {
            println!("RECV {id} {} {} route={}", req.method(), req.uri().path(), route.as_str());
        }
    }
    next.run(req).await
}

fn link_id(method: &Method, route: &str, via_gateway: bool) -> Option<&'static str> {
    match (method.as_str(), route, via_gateway) {
        ("GET", "/users", _) => Some("L01"),
        ("GET", "/users/{id}", true) => Some("L02"),
        ("POST", "/users", _) => Some("L03"),
        ("GET", "/users/{id}/wishlist", _) => Some("L04"),
        ("GET", "/users/{id}", false) => Some("L10"),
        ("GET", "/internal/buyers/{id}/verify", _) => Some("L12"),
        _ => None,
    }
}
