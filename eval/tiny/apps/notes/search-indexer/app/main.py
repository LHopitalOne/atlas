import logging

from fastapi import FastAPI, HTTPException, Query, Request, Response
from pydantic import BaseModel

from .config import settings
from .index import InvertedIndex

logger = logging.getLogger("search-indexer")

app = FastAPI(title="search-indexer")
index = InvertedIndex()


class NoteDocument(BaseModel):
    id: str
    title: str
    body: str = ""


class SearchHit(BaseModel):
    id: str
    title: str
    body: str
    score: int


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    print(f"RECV http {request.method} {path}", flush=True)
    return response


@app.post("/index", status_code=202)
def index_note(doc: NoteDocument) -> dict:
    index.add(doc.id, doc.title, doc.body)
    return {"indexed": doc.id}


@app.delete("/index/{note_id}", status_code=204)
def remove_note(note_id: str) -> Response:
    if not index.remove(note_id):
        raise HTTPException(status_code=404, detail="note not indexed")
    return Response(status_code=204)


@app.get("/search", response_model=list[SearchHit])
def search(q: str = Query(..., min_length=1), limit: int = settings.max_results) -> list[dict]:
    return index.search(q, min(limit, settings.max_results))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
