import unittest

from atlas_bridge.core.http import Protocol
from atlas_bridge.usecases.link import LinkFinder

from .support import Channels

GRPC = Protocol.GRPC

CLIENT = (
    "const grpc = require('@grpc/grpc-js');\n"
    "const protoLoader = require('@grpc/proto-loader');\n"
    "const definition = protoLoader.loadSync('billing.proto');\n"
    'const { billing } = grpc.loadPackageDefinition(definition);\n'
    'class BillingClient {\n'
    "  constructor(address = process.env.BILLING_ADDR || 'billing:50051') {\n"
    '    this.stub = new billing.v1.Invoices(address, grpc.credentials.createInsecure());\n'
    '  }\n'
    '  charge(req) {\n'
    '    return new Promise((ok, fail) => this.stub.Charge(req, (e, r) => (e ? fail(e) : ok(r))));\n'
    '  }\n'
    '  refund(req, cb) {\n'
    '    this.stub.refundPayment(req, cb);\n'
    '  }\n'
    '  close() {\n'
    '    this.stub.close();\n'
    '  }\n'
    '}\n'
    'module.exports = new BillingClient();\n'
)

SERVER = (
    "import * as grpc from '@grpc/grpc-js';\n"
    "import * as loader from '@grpc/proto-loader';\n"
    "const proto = grpc.loadPackageDefinition(loader.loadSync('billing.proto'));\n"
    'const handlers = {\n'
    '  Charge(call, callback) { callback(null, {}); },\n'
    '  RefundPayment: (call, callback) => callback(null, {}),\n'
    '};\n'
    'const server = new grpc.Server();\n'
    'server.addService(proto.billing.v1.Invoices.service, handlers);\n'
)


class GrpcClientTest(unittest.TestCase):
    def test_methods_of_a_client_made_from_a_package_definition(self):
        found = Channels.of(CLIENT, 'src/billingClient.js')
        self.assertEqual(
            found.calls,
            [
                (GRPC, 'CALL', '/invoices/charge', 'src/billingClient.js', 10),  # paths are compared without case
                (GRPC, 'CALL', '/invoices/refundpayment', 'src/billingClient.js', 13),
            ],
        )
        self.assertIn('billing.v1.Invoices', found.call('/invoices/charge').hints)

    def test_a_method_name_passed_to_a_generic_helper(self):
        found = Channels.of(
            "const grpc = require('@grpc/grpc-js');\n"
            "const pkg = grpc.loadPackageDefinition(require('@grpc/proto-loader').loadSync('stock.proto')).stock;\n"
            'class Stock {\n'
            "  constructor() { this.stub = new pkg.Stock('stock:50051', grpc.credentials.createInsecure()); }\n"
            "  reserve(sku) { return this.unary('Reserve', { sku }); }\n"
            "  release(id) { return this.unary('Release', { id }); }\n"
            '  unary(method, request) {\n'
            '    return new Promise((ok) => this.stub[method](request, (e, r) => ok(r)));\n'
            '  }\n'
            '}\n',
        )
        self.assertEqual(
            [(path, line) for _, _, path, _, line in found.calls], [('/stock/reserve', 8), ('/stock/release', 8)]
        )

    def test_a_constructor_not_from_a_package_definition_is_not_a_client(self):
        found = Channels.of("const grpc = require('@grpc/grpc-js');\nconst c = new things.Thing();\nc.Do({});\n")
        self.assertEqual(found.calls, [])


class GrpcServerTest(unittest.TestCase):
    def test_each_implemented_method_is_a_route(self):
        found = Channels.of(SERVER, 'src/server.ts')
        self.assertEqual(
            found.routes,
            [
                (GRPC, ['CALL'], '/invoices/charge', 'src/server.ts', 9),
                (GRPC, ['CALL'], '/invoices/refundpayment', 'src/server.ts', 9),
            ],
        )

    def test_a_client_links_to_the_server_of_another_repository(self):
        client = Channels({'src/billingClient.js': CLIENT}, repo='checkout').extraction
        server = Channels({'src/server.ts': SERVER}, repo='ledger').extraction
        links = LinkFinder(['checkout', 'ledger']).find(client.extend(server))
        self.assertEqual(
            sorted((lk.source, lk.target, str(lk.call.path), lk.route.line) for lk in links),
            [('checkout', 'ledger', '/invoices/charge', 9), ('checkout', 'ledger', '/invoices/refundpayment', 9)],
        )


if __name__ == '__main__':
    unittest.main()
