import logging
import sys

import uvicorn
from fastapi import FastAPI, Request

from app.routers import menus, orders
from app.settings import get_settings

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

app = FastAPI(title="restaurant")
app.include_router(menus.router)
app.include_router(orders.router)


@app.middleware("http")
async def log_received(request: Request, call_next):
    response = await call_next(request)
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    if path != "/healthz":
        print(f"RECV http {request.method} {path}", flush=True)
    return response


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.restaurant_host, port=settings.restaurant_port)
