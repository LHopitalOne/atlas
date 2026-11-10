mod internal;
mod users;
mod wishlist;

use axum::Router;

use crate::store::AppState;

pub fn router() -> Router<AppState> {
    Router::new()
        .nest("/users", users::router())
        .nest("/internal", internal::router())
}
