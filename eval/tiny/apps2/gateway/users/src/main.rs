mod links;
mod routes;
mod store;

use std::net::SocketAddr;

use axum::middleware;

use crate::store::AppState;

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(43020);

    let app = routes::router()
        .layer(middleware::from_fn(links::log_received))
        .with_state(AppState::seeded());

    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("failed to bind users port");
    println!("users listening on http://{addr}");
    axum::serve(listener, app).await.expect("users server crashed");
}
