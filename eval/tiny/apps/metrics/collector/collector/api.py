import logging

from aiohttp import web

from .store import MetricStore

log = logging.getLogger(__name__)

routes = web.RouteTableDef()
STORE_KEY = web.AppKey("store", MetricStore)


@web.middleware
async def access_log(request: web.Request, handler):
    resource = request.match_info.route.resource
    path = resource.canonical if resource is not None else request.path
    log.info("RECV http %s %s", request.method, path)
    return await handler(request)


@routes.get("/healthz")
async def healthz(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


@routes.get("/api/metrics")
async def list_metrics(request: web.Request) -> web.Response:
    store = request.app[STORE_KEY]
    return web.json_response({"metrics": store.names()})


@routes.get("/api/metrics/{name}")
async def get_series(request: web.Request) -> web.Response:
    store = request.app[STORE_KEY]
    name = request.match_info["name"]
    limit = int(request.query.get("limit", "100"))
    points = store.series(name, limit=limit)
    if points is None:
        raise web.HTTPNotFound(reason=f"unknown metric {name}")
    return web.json_response({"name": name, "points": [p.to_dict() for p in points]})


@routes.get("/api/metrics/{name}/summary")
async def get_summary(request: web.Request) -> web.Response:
    summary = request.app[STORE_KEY].summary(request.match_info["name"])
    if summary is None:
        raise web.HTTPNotFound()
    return web.json_response(summary)


@routes.post("/api/annotations")
async def create_annotation(request: web.Request) -> web.Response:
    body = await request.json()
    if not body.get("text"):
        raise web.HTTPBadRequest(reason="text is required")
    note = request.app[STORE_KEY].annotate(body["text"], body.get("ts"), body.get("author"))
    return web.json_response({"text": note.text, "ts": note.timestamp}, status=201)


def create_app(store: MetricStore) -> web.Application:
    app = web.Application(middlewares=[access_log])
    app[STORE_KEY] = store
    app.add_routes(routes)
    return app
