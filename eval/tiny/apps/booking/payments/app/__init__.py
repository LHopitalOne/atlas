import logging

from flask import Flask

from .config import Config
from .ledger import Ledger
from .middleware import register_request_logging
from .routes import bp as charges_bp


def create_app(config: type[Config] = Config) -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    app = Flask(__name__)
    app.config.from_object(config)
    app.extensions["ledger"] = Ledger(decline_above_cents=app.config["DECLINE_ABOVE_CENTS"])

    register_request_logging(app)
    app.register_blueprint(charges_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
