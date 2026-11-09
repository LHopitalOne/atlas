import logging
import signal
from concurrent import futures

import grpc

import inventory_pb2
import inventory_pb2_grpc
import settings
from events import StockEventPublisher
from store import OutOfStock, StockStore, UnknownReservation, UnknownSku

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("inventory")


class AccessLogInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        full_method = handler_call_details.method.lstrip("/")
        log.info("RECV grpc %s %s", full_method.rsplit("/", 1)[-1], full_method)
        return continuation(handler_call_details)


class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    def __init__(self, store: StockStore, events: StockEventPublisher):
        self._store = store
        self._events = events

    def Reserve(self, request, context):
        try:
            reservation, level = self._store.reserve(request.sku, request.quantity, request.order_id)
        except UnknownSku:
            context.abort(grpc.StatusCode.NOT_FOUND, f"unknown sku {request.sku}")
        except OutOfStock as exc:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))

        if level.available <= settings.LOW_STOCK_THRESHOLD:
            self._events.stock_low(level.sku, level.available, settings.LOW_STOCK_THRESHOLD)

        return inventory_pb2.ReserveResponse(reservation_id=reservation.id, available=level.available)

    def Release(self, request, context):
        try:
            _, level = self._store.release(request.reservation_id)
        except UnknownReservation:
            context.abort(grpc.StatusCode.NOT_FOUND, f"unknown reservation {request.reservation_id}")
        return inventory_pb2.ReleaseResponse(released=True, available=level.available)

    def GetStock(self, request, context):
        try:
            level = self._store.level(request.sku)
        except UnknownSku:
            context.abort(grpc.StatusCode.NOT_FOUND, f"unknown sku {request.sku}")
        return inventory_pb2.StockLevel(
            sku=level.sku,
            on_hand=level.on_hand,
            reserved=level.reserved,
            available=level.available,
        )


def serve() -> None:
    events = StockEventPublisher()
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=settings.GRPC_WORKERS),
        interceptors=[AccessLogInterceptor()],
    )
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(
        InventoryServicer(StockStore(settings.SEED_STOCK), events), server
    )
    address = f"{settings.GRPC_HOST}:{settings.GRPC_PORT}"
    server.add_insecure_port(address)
    server.start()
    log.info("inventory gRPC listening on %s", address)

    def shutdown(*_):
        server.stop(grace=2)
        events.close()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
