mod api;
mod book;
mod consumer;

use std::env;
use std::sync::Arc;

use book::Book;

#[tokio::main]
async fn main() {
    let brokers = env::var("KAFKA_BROKERS").unwrap_or_else(|_| "localhost:46092".to_string());
    let port = env::var("LEDGER_PORT").unwrap_or_else(|_| "46030".to_string());

    let book = Arc::new(Book::default());

    let consumer_book = Arc::clone(&book);
    tokio::spawn(async move {
        consumer::run(&brokers, consumer_book).await;
    });

    let listener = tokio::net::TcpListener::bind(format!("127.0.0.1:{port}"))
        .await
        .expect("bind ledger port");
    println!("ledger listening on {port}");
    axum::serve(listener, api::router(book))
        .await
        .expect("ledger http server");
}
