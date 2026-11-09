use std::env;
use std::time::Duration;

#[derive(Debug, Clone)]
pub struct Config {
    pub collector_addr: String,
    pub statsd_addr: String,
    pub metric_prefix: String,
    pub hostname: String,
    pub interval: Duration,
    pub iterations: Option<u32>,
}

fn env_or(key: &str, default: &str) -> String {
    env::var(key).unwrap_or_else(|_| default.to_string())
}

impl Config {
    pub fn from_env() -> Self {
        let host = env_or("COLLECTOR_HOST", "127.0.0.1");
        let tcp_port = env_or("COLLECTOR_TCP_PORT", "41710");
        let statsd_port = env_or("COLLECTOR_STATSD_PORT", "41711");
        let interval_ms: u64 = env_or("AGENT_INTERVAL_MS", "5000").parse().unwrap_or(5000);

        Config {
            collector_addr: format!("{host}:{tcp_port}"),
            statsd_addr: format!("{host}:{statsd_port}"),
            metric_prefix: env_or("AGENT_METRIC_PREFIX", "agent"),
            hostname: env_or("HOSTNAME", "localhost"),
            interval: Duration::from_millis(interval_ms),
            iterations: env::var("AGENT_ITERATIONS").ok().and_then(|v| v.parse().ok()),
        }
    }
}
