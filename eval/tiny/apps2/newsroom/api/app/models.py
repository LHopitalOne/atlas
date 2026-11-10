from pydantic import BaseModel, Field


class Story(BaseModel):
    id: int
    title: str
    by: str | None = None
    score: int = 0
    url: str | None = None
    descendants: int = 0
    kids: list[int] = Field(default_factory=list)


class SummaryRequest(BaseModel):
    story_id: int


class SummaryJob(BaseModel):
    job_id: str
    story_id: int
    status: str = "queued"


class SummaryResultIn(BaseModel):
    story_id: int
    summary: str
    comment_count: int
    worker: str


class Summary(BaseModel):
    story_id: int
    status: str
    summary: str | None = None
    comment_count: int = 0
