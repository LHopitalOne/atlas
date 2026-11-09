import logging
import re

logger = logging.getLogger("hr.requests")

_NAMED_GROUP = re.compile(r"\(\?P<(?P<name>\w+)>[^)]*\)")
_CONVERTER = re.compile(r"<(?:\w+:)?(?P<name>\w+)>")


def _route_template(route: str) -> str:
    route = route.replace("^", "").replace("$", "")
    route = _NAMED_GROUP.sub(lambda m: "{" + m.group("name") + "}", route)
    route = _CONVERTER.sub(lambda m: "{" + m.group("name") + "}", route)
    return "/" + route


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        match = getattr(request, "resolver_match", None)
        route = _route_template(match.route) if match else request.path
        logger.info("RECV http %s %s", request.method, route)
        return response
