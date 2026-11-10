use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::get;
use axum::{Json, Router};
use serde_json::{json, Value};

use crate::store::AppState;

/// Service-to-service routes; not exposed through the edge gateway.
pub fn router() -> Router<AppState> {
    Router::new().route("/buyers/{id}/verify", get(verify_buyer))
}

async fn verify_buyer(State(state): State<AppState>, Path(id): Path<u64>) -> Result<Json<Value>, StatusCode> {
    let user = state.find(id).await.ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(json!({ "id": user.id, "eligible": user.verified })))
}
