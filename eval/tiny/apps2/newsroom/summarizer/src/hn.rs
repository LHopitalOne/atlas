use reqwest::Client;

use crate::model::HnComment;

/// Thin wrapper over the public Hacker News Firebase API.
pub struct HackerNews {
    http: Client,
    base: String,
}

impl HackerNews {
    pub fn new(http: Client, base: impl Into<String>) -> Self {
        Self { http, base: base.into().trim_end_matches('/').to_string() }
    }

    pub async fn comment(&self, id: i64) -> reqwest::Result<Option<HnComment>> {
        let url = format!("{}/item/{}.json", self.base, id);
        let resp = self.http.get(&url).send().await?.error_for_status()?;
        println!("RECV S02 GET hacker-news.firebaseio.com/v0/item/{id}.json (caller summarizer)");
        resp.json::<Option<HnComment>>().await
    }
}
