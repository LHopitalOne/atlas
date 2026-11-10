use reqwest::Client;

use crate::model::SummaryResult;

/// Client for the newsroom api's internal callback endpoints.
pub struct NewsroomApi {
    http: Client,
    base_url: String,
}

impl NewsroomApi {
    pub fn new(http: Client, base_url: &str) -> Self {
        Self { http, base_url: base_url.trim_end_matches('/').to_string() }
    }

    fn endpoint(&self, path: &str) -> String {
        format!("{}/api/v1{}", self.base_url, path)
    }

    pub async fn submit_summary(&self, job_id: &str, result: &SummaryResult) -> reqwest::Result<()> {
        let url = self.endpoint(&format!("/internal/summaries/{job_id}/result"));
        self.http
            .post(url)
            .json(result)
            .send()
            .await?
            .error_for_status()?;
        Ok(())
    }
}
