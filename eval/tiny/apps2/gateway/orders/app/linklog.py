from flask import Flask, request

# (method, url rule, arrived through the edge proxy?) -> link id
LINKS: dict[tuple[str, str, bool], str] = {
    ("GET", "/v1/orders", True): "L05",
    ("POST", "/v1/orders", True): "L06",
    ("GET", "/v1/orders/<int:order_id>", True): "L07",
    ("GET", "/v1/orders/<int:order_id>/items", True): "L08",
    ("GET", "/v1/orders", False): "L11",
}


def install_link_log(app: Flask) -> None:
    @app.before_request
    def _log_received_link() -> None:
        if request.url_rule is None:
            return
        via_gateway = "X-Forwarded-For" in request.headers
        link_id = LINKS.get((request.method, request.url_rule.rule, via_gateway))
        if link_id:
            print(f"RECV {link_id} {request.method} {request.path} rule={request.url_rule.rule}", flush=True)
