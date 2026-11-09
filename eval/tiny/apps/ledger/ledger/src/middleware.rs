use axum::extract::{MatchedPath, Request};
use axum::middleware::Next;
use axum::response::Response;

pub async fn log_received(matched: MatchedPath, req: Request, next: Next) -> Response {
    eprintln!("RECV http {} {}", req.method(), matched.as_str());
    next.run(req).await
}
