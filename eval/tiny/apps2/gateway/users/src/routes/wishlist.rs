use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::get;
use axum::{Json, Router};

use crate::store::{AppState, WishlistItem};

pub fn router() -> Router<AppState> {
    Router::new().route("/", get(get_wishlist))
}

async fn get_wishlist(
    State(state): State<AppState>,
    Path(id): Path<u64>,
) -> Result<Json<Vec<WishlistItem>>, StatusCode> {
    match state.find(id).await {
        Some(user) => Ok(Json(state.wishlist_for(user.id))),
        None => Err(StatusCode::NOT_FOUND),
    }
}
