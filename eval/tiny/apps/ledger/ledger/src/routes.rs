use std::sync::Arc;

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{middleware, Json, Router};
use serde::Deserialize;
use serde_json::{json, Value};

use crate::error::LedgerError;
use crate::middleware::log_received;
use crate::store::{Account, Store, Transfer};

type AppState = Arc<Store>;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/accounts", post(create_account))
        .route("/accounts/{account_id}", get(get_account))
        .route("/accounts/{account_id}/balance", get(get_balance))
        .route("/accounts/{account_id}/transfers", get(list_transfers))
        .route("/transfers", post(create_transfer))
        .route_layer(middleware::from_fn(log_received))
        .with_state(state)
}

#[derive(Deserialize)]
struct NewAccount {
    name: String,
    currency: Option<String>,
    #[serde(default)]
    allow_overdraft: bool,
}

#[derive(Deserialize)]
struct NewTransfer {
    source_id: u64,
    destination_id: u64,
    amount: i64,
    #[serde(default)]
    reference: String,
}

async fn health() -> Json<Value> {
    Json(json!({ "status": "ok" }))
}

async fn create_account(
    State(store): State<AppState>,
    Json(body): Json<NewAccount>,
) -> (StatusCode, Json<Account>) {
    let account = store.open_account(body.name, body.currency, body.allow_overdraft);
    (StatusCode::CREATED, Json(account))
}

async fn get_account(
    State(store): State<AppState>,
    Path(account_id): Path<u64>,
) -> Result<Json<Account>, LedgerError> {
    store.account(account_id).map(Json)
}

async fn get_balance(
    State(store): State<AppState>,
    Path(account_id): Path<u64>,
) -> Result<Json<Value>, LedgerError> {
    let account = store.account(account_id)?;
    Ok(Json(json!({
        "account_id": account.id,
        "balance": account.balance,
        "currency": account.currency,
    })))
}

async fn list_transfers(
    State(store): State<AppState>,
    Path(account_id): Path<u64>,
) -> Result<Json<Vec<Transfer>>, LedgerError> {
    store.transfers_for(account_id).map(Json)
}

async fn create_transfer(
    State(store): State<AppState>,
    Json(body): Json<NewTransfer>,
) -> Result<(StatusCode, Json<Transfer>), LedgerError> {
    let transfer = store.post_transfer(body.source_id, body.destination_id, body.amount, body.reference)?;
    Ok((StatusCode::CREATED, Json(transfer)))
}
