from fastapi import APIRouter

from app.routers import internal, stories, summaries

api_router = APIRouter()
api_router.include_router(stories.router)
api_router.include_router(summaries.router)
api_router.include_router(internal.router)

__all__ = ["api_router"]
