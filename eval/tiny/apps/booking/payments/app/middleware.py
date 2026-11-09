import logging
import re

from flask import Flask, request

logger = logging.getLogger("payments.requests")

_RULE_PARAM = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")
QUIET_ENDPOINTS = {"health"}


def register_request_logging(app: Flask) -> None:
    @app.before_request
    def log_request() -> None:
        if request.url_rule is None or request.endpoint in QUIET_ENDPOINTS:
            return
        path = _RULE_PARAM.sub(r"{\1}", request.url_rule.rule)
        logger.info("RECV http %s %s", request.method, path)
