import unittest

from atlas_bridge.core.http import ANY, Protocol

from .support import extract


class GrpcTest(unittest.TestCase):
    def test_registered_servicer_methods_are_routes(self):
        ex = extract(
            {
                'app/service.py': """
                from app.pb import moderation_pb2_grpc

                class ModerationService(moderation_pb2_grpc.ModerationServicer):
                    def __init__(self):
                        self._seen = 0

                    def CheckMessage(self, request, context):
                        return None

                    def _helper(self):
                        pass

                    def Describe(self):
                        return 'not a handler: grpcio calls each method with (request, context)'
                """,
                'app/server.py': """
                import grpc
                from app.pb import moderation_pb2_grpc
                from app.service import ModerationService

                def serve():
                    server = grpc.server(None)
                    moderation_pb2_grpc.add_ModerationServicer_to_server(ModerationService(), server)
                """,
                'app/other.py': """
                class Unregistered:
                    def Reserve(self, request, context):
                        pass
                """,
            }
        )
        routes = [r for r in ex.routes if r.protocol == Protocol.GRPC]
        self.assertEqual(
            [(str(r.path), r.methods, r.handler) for r in routes],
            [('/moderation/checkmessage', frozenset({'CALL'}), 'ModerationService.CheckMessage')],
        )
        self.assertEqual((routes[0].file, routes[0].line, routes[0].framework), ('app/service.py', 8, 'grpc'))

    def test_stub_method_calls(self):
        ex = extract(
            {
                'client.py': """
                import grpc
                import inventory_pb2_grpc
                from inventory_pb2_grpc import InventoryServiceStub

                class Client:
                    def __init__(self, target):
                        self._stub = inventory_pb2_grpc.InventoryServiceStub(grpc.insecure_channel(target))

                    def reserve(self, request):
                        return self._stub.Reserve(request, timeout=5)

                def stock(request):
                    stub = InventoryServiceStub(grpc.insecure_channel('x'))
                    return stub.GetStock.future(request)

                def unrelated(thing):
                    return thing.Reserve()
                """,
            }
        )
        calls = {(c.protocol, c.method, str(c.path), c.function) for c in ex.calls}
        self.assertEqual(
            calls,
            {
                (Protocol.GRPC, 'CALL', '/inventoryservice/reserve', 'Client.reserve'),
                (Protocol.GRPC, 'CALL', '/inventoryservice/getstock', 'stock'),
            },
        )


class StrawberryTest(unittest.TestCase):
    SCHEMA = """
    import strawberry

    @strawberry.type
    class Room:
        id: strawberry.ID
        nightly_rate: int

    @strawberry.type
    class Query:
        room_count: int
        secret: strawberry.Private[str]

        @strawberry.field
        def rooms(self, city: str | None = None) -> list[Room]:
            return []

        @strawberry.field(name='findRoom')
        def find(self, id: strawberry.ID) -> Room:
            return None

    @strawberry.type
    class Writes:
        @strawberry.mutation
        async def book_room(self, room_id: strawberry.ID) -> Room:
            return None

    schema = strawberry.Schema(query=Query, mutation=Writes{config})
    """

    def fields(self, config=''):
        ex = extract({'app/schema.py': self.SCHEMA.replace('{config}', config)})
        return {(str(r.path), r.handler) for r in ex.routes if r.protocol == Protocol.GRAPHQL}, ex

    def test_root_fields_in_camel_case(self):
        found, ex = self.fields()
        self.assertEqual(
            found,
            {
                ('/roomcount', 'Query.room_count'),
                ('/rooms', 'Query.rooms'),
                ('/findroom', 'Query.find'),
                ('/bookroom', 'Writes.book_room'),
            },
        )
        rooms = next(r for r in ex.routes if r.handler == 'Query.rooms')
        self.assertEqual((rooms.line, rooms.methods, rooms.framework), (15, frozenset({ANY}), 'strawberry'))

    def test_camel_case_turned_off(self):
        found, _ = self.fields(', config=StrawberryConfig(auto_camel_case=False)')
        self.assertIn(('/book_room', 'Writes.book_room'), found)

    def test_camel_case_turned_off_through_a_config_name(self):
        ex = extract(
            {
                'app/schema.py': self.SCHEMA.replace('{config}', ', config=CONFIG').replace(
                    'import strawberry\n',
                    'import strawberry\nfrom strawberry.schema.config import StrawberryConfig\n'
                    'CONFIG = StrawberryConfig(auto_camel_case = False)\n',
                )
            }
        )
        found = {str(r.path) for r in ex.routes if r.protocol == Protocol.GRAPHQL}
        self.assertIn('/book_room', found)

    def test_only_types_a_schema_names_are_roots(self):
        ex = extract(
            {
                'app/types.py': """
                import strawberry

                @strawberry.type
                class Query:
                    rooms: list[str]
                """,
                'app/schema.py': """
                import strawberry

                @strawberry.type
                class Root:
                    rooms_left: int = strawberry.field(name='vacancies')
                    nightly_rate: int

                schema = strawberry.Schema(query=Root)
                """,
            }
        )
        found = {(str(r.path), r.handler) for r in ex.routes if r.protocol == Protocol.GRAPHQL}
        self.assertEqual(found, {('/vacancies', 'Root.rooms_left'), ('/nightlyrate', 'Root.nightly_rate')})

    def test_camel_case_matches_strawberry(self):
        from atlas_bridge.adapters.treesitter.python.channels import StrawberryFields

        self.assertEqual(StrawberryFields.camel_case('cancel_booking'), 'cancelBooking')
        self.assertEqual(StrawberryFields.camel_case('get_URL_path'), 'getUrlPath')
        self.assertEqual(StrawberryFields.camel_case('rooms'), 'rooms')


if __name__ == '__main__':
    unittest.main()
