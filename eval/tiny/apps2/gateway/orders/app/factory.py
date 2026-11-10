import os

from flask import Flask

from app.blueprints.orders import orders_bp
from app.clients.fx import FxClient
from app.clients.users import UsersClient
from app.linklog import install_link_log
from app.store import OrderStore


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["USERS_SERVICE_URL"] = os.environ.get("USERS_SERVICE_URL", "http://127.0.0.1:43020")

    app.extensions["orders.store"] = OrderStore()
    app.extensions["orders.users"] = UsersClient(app.config["USERS_SERVICE_URL"])
    app.extensions["orders.fx"] = FxClient()

    app.register_blueprint(orders_bp)
    install_link_log(app)
    return app
