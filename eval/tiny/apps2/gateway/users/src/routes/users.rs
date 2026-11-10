use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::get;
use axum::{Json, Router};

use crate::store::{AppState, NewUser, User};

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", get(list_users).post(create_user))
        .route("/{id}", get(get_user))
        .nest("/{id}/wishlist", super::wishlist::router())
}

async fn list_users(State(state): State<AppState>) -> Json<Vec<User>> {
    Json(state.users.read().await.clone())
}

async fn get_user(State(state): State<AppState>, Path(id): Path<u64>) -> Result<Json<User>, StatusCode> {
    state.find(id).await.map(Json).ok_or(StatusCode::NOT_FOUND)
}

async fn create_user(State(state): State<AppState>, Json(body): Json<NewUser>) -> (StatusCode, Json<User>) {
    let mut users = state.users.write().await;
    let user = User {
        id: users.iter().map(|u| u.id).max().unwrap_or(0) + 1,
        name: body.name,
        email: body.email,
        verified: false,
    };
    users.push(user.clone());
    (StatusCode::CREATED, Json(user))
}
