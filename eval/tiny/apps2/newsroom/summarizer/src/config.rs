use std::env;

/// Runtime settings, read once from the environment at startup.
#[derive(Debug, Clone)]
pub struct Settings {
    pub redis_url: String,
    pub api_base_url: String,
    pub hn_base_url: String,
    pub jobs_queue: String,
    pub done_channel: String,
    pub max_comments: usize,
}

impl Settings {
    pub fn from_env() -> Self {
        Self {
            redis_url: env::var("REDIS_URL").unwrap_or_else(|_| "redis://127.0.0.1:6379/0".into()),
            api_base_url: env::var("NEWSROOM_API_URL").unwrap_or_else(|_| "http://127.0.0.1:8000".into()),
            hn_base_url: env::var("HN_API_BASE")
                .unwrap_or_else(|_| "https://hacker-news.firebaseio.com/v0".into()),
            jobs_queue: env::var("SUMMARY_JOBS_QUEUE").unwrap_or_else(|_| "newsroom:summaries:jobs".into()),
            done_channel: env::var("SUMMARY_DONE_CHANNEL")
                .unwrap_or_else(|_| "newsroom:summaries:done".into()),
            max_comments: env::var("SUMMARY_MAX_COMMENTS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(3),
        }
    }
}
