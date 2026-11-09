import logging
import re

from dotenv import load_dotenv
from flask import Flask, request

from billing.extensions import init_ledger

_URL_PARAM = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")

log = logging.getLogger("billing")


def create_app() -> Flask:
    load_dotenv()
    from billing.config import Settings
    from billing.customers import bp as customers_bp

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    app = Flask(__name__)
    app.config.from_object(Settings)
    init_ledger(app)
    app.register_blueprint(customers_bp)

    @app.before_request
    def log_received():
        if request.url_rule is not None:
            route = _URL_PARAM.sub(r"{\1}", request.url_rule.rule)
            log.info("RECV http %s %s", request.method, route)

    return app
