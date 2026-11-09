import grpc


class ReceiveLogInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        service, method = handler_call_details.method.lstrip("/").split("/", 1)
        print(f"RECV grpc {method} {service}/{method}", flush=True)
        return continuation(handler_call_details)
