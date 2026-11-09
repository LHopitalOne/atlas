use std::env;

pub struct Config {
    pub bind_addr: String,
    pub default_currency: String,
}

impl Config {
    pub fn from_env() -> Self {
        let host = env::var("LEDGER_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
        let port = env::var("LEDGER_PORT").unwrap_or_else(|_| "41410".to_string());
        Self {
            bind_addr: format!("{host}:{port}"),
            default_currency: env::var("LEDGER_DEFAULT_CURRENCY").unwrap_or_else(|_| "USD".to_string()),
        }
    }
}
