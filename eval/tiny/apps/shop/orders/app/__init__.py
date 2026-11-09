import logging
import re

from flask import Flask, request

from .catalog_client import CatalogClient
from .config import Config
from .events import OrderEventPublisher
from .routes import bp
from .store import OrderStore

logger = logging.getLogger("orders")
_RULE_ARG = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")


def create_app(config: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    app.extensions["catalog"] = CatalogClient(
        app.config["CATALOG_URL"], timeout=app.config["CATALOG_TIMEOUT"]
    )
    app.extensions["order_events"] = OrderEventPublisher(
        app.config["REDIS_URL"], app.config["ORDER_EVENTS_CHANNEL"]
    )
    app.extensions["order_store"] = OrderStore()
    app.register_blueprint(bp)

    @app.after_request
    def log_request(response):
        if request.url_rule is not None:
            path = _RULE_ARG.sub(r"{\1}", request.url_rule.rule)
            logger.info("RECV http %s %s", request.method, path)
        return response

    return app
