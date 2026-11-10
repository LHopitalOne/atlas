use std::sync::Arc;

use axum::extract::{Path, State};
use axum::routing::get;
use axum::{Json, Router};

use crate::book::{Balance, Book};

pub fn router(book: Arc<Book>) -> Router {
    Router::new()
        .route("/balances/{merchant_id}", get(get_balance))
        .route("/healthz", get(|| async { "ok" }))
        .with_state(book)
}

async fn get_balance(State(book): State<Arc<Book>>, Path(merchant_id): Path<String>) -> Json<Balance> {
    println!("RECV L07 http GET /balances/{merchant_id}");
    Json(book.get(&merchant_id))
}
