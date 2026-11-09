import logging

from fastapi import FastAPI, Request

from .routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("catalog")

app = FastAPI(title="catalog")
app.include_router(router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    route = request.scope.get("route")
    if route is not None:
        logger.info("RECV http %s %s", request.method, route.path)
    return response
