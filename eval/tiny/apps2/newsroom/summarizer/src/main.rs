mod api_client;
mod config;
mod hn;
mod model;
mod summarize;

use std::time::Duration;

use redis::AsyncCommands;
use redis::aio::MultiplexedConnection;

use crate::api_client::NewsroomApi;
use crate::config::Settings;
use crate::hn::HackerNews;
use crate::model::{DoneEvent, SummaryJob, SummaryResult};

type BoxError = Box<dyn std::error::Error + Send + Sync>;

struct Worker {
    settings: Settings,
    hn: HackerNews,
    api: NewsroomApi,
    publisher: MultiplexedConnection,
}

impl Worker {
    async fn handle(&mut self, job: SummaryJob) -> Result<(), BoxError> {
        let mut comments = Vec::new();
        for kid in job.kids.iter().take(self.settings.max_comments) {
            if let Some(comment) = self.hn.comment(*kid).await? {
                comments.push(comment);
            }
        }
        let result = SummaryResult {
            story_id: job.story_id,
            summary: summarize::summarize(&job.title, &comments),
            comment_count: comments.len(),
            worker: "summarizer-rs".into(),
        };
        self.api.submit_summary(&job.job_id, &result).await?;

        let event = serde_json::to_string(&DoneEvent { job_id: &job.job_id, story_id: job.story_id })?;
        let receivers: i64 = self.publisher.publish(&self.settings.done_channel, event).await?;
        println!("summarizer: job {} done, notified {receivers} subscriber(s)", job.job_id);
        Ok(())
    }
}

async fn run(settings: Settings) -> Result<(), BoxError> {
    let client = redis::Client::open(settings.redis_url.as_str())?;
    // BRPOP blocks its connection, so jobs and notifications use separate ones.
    let mut jobs_conn = client.get_multiplexed_async_connection().await?;
    let publisher = client.get_multiplexed_async_connection().await?;

    let http = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .user_agent("newsroom-summarizer/0.1")
        .build()?;
    let mut worker = Worker {
        hn: HackerNews::new(http.clone(), settings.hn_base_url.clone()),
        api: NewsroomApi::new(http, &settings.api_base_url),
        publisher,
        settings,
    };

    println!(
        "summarizer: waiting on {} (api at {})",
        worker.settings.jobs_queue, worker.settings.api_base_url
    );
    loop {
        let popped: Option<(String, String)> = jobs_conn.brpop(&worker.settings.jobs_queue, 5.0).await?;
        let Some((queue, payload)) = popped else { continue };
        let job: SummaryJob = match serde_json::from_str(&payload) {
            Ok(job) => job,
            Err(err) => {
                eprintln!("summarizer: dropping malformed job: {err}");
                continue;
            }
        };
        println!("RECV R01 CONSUME {queue} job={} story={}", job.job_id, job.story_id);
        if let Err(err) = worker.handle(job).await {
            eprintln!("summarizer: job failed: {err}");
        }
    }
}

#[tokio::main]
async fn main() {
    let settings = Settings::from_env();
    tokio::select! {
        res = run(settings) => {
            if let Err(err) = res {
                eprintln!("summarizer: fatal: {err}");
                std::process::exit(1);
            }
        }
        _ = tokio::signal::ctrl_c() => println!("summarizer: shutting down"),
    }
}
