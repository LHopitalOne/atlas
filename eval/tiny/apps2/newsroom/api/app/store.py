"""In-process summary store (the api is a single instance)."""

from app.models import Summary, SummaryResultIn


class SummaryStore:
    def __init__(self) -> None:
        self._by_story: dict[int, Summary] = {}
        self._jobs: dict[str, int] = {}

    def mark_queued(self, job_id: str, story_id: int) -> None:
        self._jobs[job_id] = story_id
        self._by_story[story_id] = Summary(story_id=story_id, status="queued")

    def complete(self, job_id: str, result: SummaryResultIn) -> Summary:
        story_id = self._jobs.pop(job_id, result.story_id)
        summary = Summary(
            story_id=story_id,
            status="done",
            summary=result.summary,
            comment_count=result.comment_count,
        )
        self._by_story[story_id] = summary
        return summary

    def mark_notified(self, story_id: int) -> None:
        if (s := self._by_story.get(story_id)) is not None and s.status == "done":
            self._by_story[story_id] = s.model_copy(update={"status": "ready"})

    def get(self, story_id: int) -> Summary | None:
        return self._by_story.get(story_id)
