use std::sync::Arc;

use serde::{Deserialize, Serialize};
use tokio::sync::RwLock;

#[derive(Clone, Serialize)]
pub struct User {
    pub id: u64,
    pub name: String,
    pub email: String,
    pub verified: bool,
}

#[derive(Clone, Serialize)]
pub struct WishlistItem {
    pub sku: String,
    pub note: String,
}

#[derive(Deserialize)]
pub struct NewUser {
    pub name: String,
    pub email: String,
}

#[derive(Clone, Default)]
pub struct AppState {
    pub users: Arc<RwLock<Vec<User>>>,
}

impl AppState {
    pub fn seeded() -> Self {
        let users = vec![
            User { id: 1, name: "Ada".into(), email: "ada@bazaarly.test".into(), verified: true },
            User { id: 2, name: "Linus".into(), email: "linus@bazaarly.test".into(), verified: true },
            User { id: 3, name: "Mallory".into(), email: "mallory@bazaarly.test".into(), verified: false },
        ];
        Self { users: Arc::new(RwLock::new(users)) }
    }

    pub async fn find(&self, id: u64) -> Option<User> {
        self.users.read().await.iter().find(|u| u.id == id).cloned()
    }

    pub fn wishlist_for(&self, id: u64) -> Vec<WishlistItem> {
        (1..=id.min(3))
            .map(|n| WishlistItem { sku: format!("SKU-{}", 100 + n), note: format!("saved #{n}") })
            .collect()
    }
}
