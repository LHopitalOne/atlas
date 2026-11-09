mod config;
mod error;
mod middleware;
mod routes;
mod store;

use std::sync::Arc;

use config::Config;
use store::Store;

#[tokio::main]
async fn main() {
    let config = Config::from_env();
    let state = Arc::new(Store::new(config.default_currency.clone()));
    let app = routes::router(state);

    let listener = tokio::net::TcpListener::bind(&config.bind_addr)
        .await
        .expect("failed to bind ledger listener");
    println!("ledger listening on {}", config.bind_addr);

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .expect("ledger server crashed");
}

async fn shutdown_signal() {
    let _ = tokio::signal::ctrl_c().await;
}
