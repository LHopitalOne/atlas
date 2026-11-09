import logging
import signal
from concurrent import futures

import grpc

from app import settings
from app.interceptors import ReceiveLogInterceptor
from app.pb import moderation_pb2_grpc
from app.service import ModerationService


def serve() -> None:
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=settings.MAX_WORKERS),
        interceptors=[ReceiveLogInterceptor()],
    )
    moderation_pb2_grpc.add_ModerationServicer_to_server(ModerationService(), server)
    address = f"{settings.GRPC_HOST}:{settings.GRPC_PORT}"
    server.add_insecure_port(address)
    server.start()
    logging.info("moderation gRPC listening on %s", address)
    signal.signal(signal.SIGTERM, lambda *_: server.stop(grace=1))
    server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    serve()
