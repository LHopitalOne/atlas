import unittest

from .support import RustRepo

CONFIG = """
use std::env;

pub struct Settings {
    pub feed_url: String,
    pub billing_url: String,
}

impl Settings {
    pub fn from_env() -> Self {
        Self {
            feed_url: env::var("FEED_URL").unwrap_or_else(|_| "https://feeds.example.org/v2/".into()),
            billing_url: env::var("BILLING_URL").unwrap_or_else(|_| "http://127.0.0.1:7100".into()),
        }
    }
}
"""
CLIENTS = """
use reqwest::Client;

pub struct Feed {
    http: Client,
    base: String,
}

impl Feed {
    pub fn new(http: Client, base: impl Into<String>) -> Self {
        Self { http, base: base.into().trim_end_matches('/').to_string() }
    }

    pub async fn item(&self, id: i64) -> reqwest::Result<()> {
        let url = format!("{}/items/{}.json", self.base, id);
        self.http.get(&url).send().await?;
        Ok(())
    }
}

pub struct Billing {
    http: Client,
    base_url: String,
}

impl Billing {
    pub fn new(http: Client, base_url: &str) -> Self {
        Self { http, base_url: base_url.to_string() }
    }

    fn endpoint(&self, path: &str) -> String {
        format!("{}/api{}", self.base_url, path)
    }

    pub async fn charge(&self, id: &str) -> reqwest::Result<()> {
        let url = self.endpoint(&format!("/charges/{id}"));
        self.http.post(url).send().await?;
        Ok(())
    }
}
"""
MAIN = """
mod clients;
mod config;

use crate::clients::{Billing, Feed};
use crate::config::Settings;

async fn run(settings: Settings) {
    let http = reqwest::Client::new();
    let feed = Feed::new(http.clone(), settings.feed_url.clone());
    let billing = Billing::new(http, &settings.billing_url);
    feed.item(1).await.unwrap();
    billing.charge("c1").await.unwrap();
}

#[tokio::main]
async fn main() {
    run(Settings::from_env()).await;
}
"""


class ConfiguredBaseTest(unittest.TestCase):
    def test_a_base_held_in_a_field_is_the_one_the_settings_give(self):
        ex = RustRepo({'src/config.rs': CONFIG, 'src/clients.rs': CLIENTS, 'src/main.rs': MAIN}).extract()
        calls = {(c.method, str(c.path)): c for c in ex.calls}
        self.assertEqual(calls['GET', '/v2/items/{id}.json'].host, 'feeds.example.org')
        charge = next(c for (m, p), c in calls.items() if m == 'POST' and p.startswith('/api/charges/'))
        self.assertIn('127.0.0.1:7100', charge.hints)


if __name__ == '__main__':
    unittest.main()
