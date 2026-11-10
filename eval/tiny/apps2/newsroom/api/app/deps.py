from fastapi import Request

from app.clients import HackerNewsClient
from app.queue import SummaryQueue
from app.store import SummaryStore


def get_hn(request: Request) -> HackerNewsClient:
    return request.app.state.hn


def get_queue(request: Request) -> SummaryQueue:
    return request.app.state.queue


def get_store(request: Request) -> SummaryStore:
    return request.app.state.store
