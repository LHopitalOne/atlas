use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;

#[derive(Debug)]
pub enum LedgerError {
    AccountNotFound(u64),
    InsufficientFunds { account_id: u64, balance: i64, amount: i64 },
    CurrencyMismatch,
    InvalidAmount,
}

impl IntoResponse for LedgerError {
    fn into_response(self) -> Response {
        let (status, code, message) = match self {
            LedgerError::AccountNotFound(id) => {
                (StatusCode::NOT_FOUND, "account_not_found", format!("account {id} does not exist"))
            }
            LedgerError::InsufficientFunds { account_id, balance, amount } => (
                StatusCode::UNPROCESSABLE_ENTITY,
                "insufficient_funds",
                format!("account {account_id} has {balance}, cannot debit {amount}"),
            ),
            LedgerError::CurrencyMismatch => (
                StatusCode::UNPROCESSABLE_ENTITY,
                "currency_mismatch",
                "accounts use different currencies".to_string(),
            ),
            LedgerError::InvalidAmount => (
                StatusCode::BAD_REQUEST,
                "invalid_amount",
                "amount must be positive".to_string(),
            ),
        };
        (status, Json(json!({ "error": code, "message": message }))).into_response()
    }
}
