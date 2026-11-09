import logging
import os

from app import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("ORDERS_HOST", "127.0.0.1"),
        port=int(os.getenv("ORDERS_PORT", "41002")),
    )
