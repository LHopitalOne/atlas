use serde::{Deserialize, Serialize};

/// A job as enqueued by the api (`app/queue.py`).
#[derive(Debug, Deserialize)]
pub struct SummaryJob {
    pub job_id: String,
    pub story_id: i64,
    pub title: String,
    #[serde(default)]
    pub kids: Vec<i64>,
}

/// Minimal shape of a Hacker News comment item.
#[derive(Debug, Deserialize)]
pub struct HnComment {
    #[serde(default)]
    pub by: Option<String>,
    #[serde(default)]
    pub text: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct SummaryResult {
    pub story_id: i64,
    pub summary: String,
    pub comment_count: usize,
    pub worker: String,
}

#[derive(Debug, Serialize)]
pub struct DoneEvent<'a> {
    pub job_id: &'a str,
    pub story_id: i64,
}
