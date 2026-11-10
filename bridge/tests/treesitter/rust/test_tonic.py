import unittest

from atlas_bridge.core.http import Protocol

from .support import RustRepo

SERVICE = """
use tonic::{Request, Response, Status};

use crate::proto::shipping_quotes_server::ShippingQuotes;
use crate::proto::{QuoteReply, QuoteRequest};

pub struct Quotes;

#[tonic::async_trait]
impl ShippingQuotes for Quotes {
    type WatchStream = ReceiverStream<Result<QuoteReply, Status>>;

    async fn get_quote(&self, request: Request<QuoteRequest>) -> Result<Response<QuoteReply>, Status> {
        todo!()
    }

    async fn watch(&self, request: Request<QuoteRequest>) -> Result<Response<Self::WatchStream>, Status> {
        todo!()
    }
}

impl Quotes {
    pub fn helper(&self) {}
}
"""

QUALIFIED = """
pub mod pb {
    tonic::include_proto!("billing.v2");
}

struct Ledger;

#[tonic::async_trait]
impl pb::ledger_server::Ledger for Ledger {
    async fn post_entry(&self, request: tonic::Request<pb::Entry>) -> Result<tonic::Response<pb::Ack>, tonic::Status> {
        todo!()
    }
}
"""

NOT_TONIC = """
use tonic::Status;
use crate::store::reader_server::Writer;

struct Mine;

impl Writer for Mine {
    fn write(&self) {}
}

impl std::fmt::Display for Mine {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result { Ok(()) }
}
"""

TESTED = """
use tonic::Request;

#[cfg(test)]
mod tests {
    use crate::pb::echo_server::Echo;
    struct Fake;
    #[tonic::async_trait]
    impl Echo for Fake {
        async fn say(&self, r: Request<()>) -> Result<(), ()> { Ok(()) }
    }
}
"""


class TonicServiceTest(unittest.TestCase):
    def test_each_fn_of_a_generated_service_trait_impl_is_a_method(self):
        routes = RustRepo({'src/service.rs': SERVICE}).extract().routes
        self.assertEqual(
            {(str(r.path), r.line, r.handler) for r in routes},
            {('/shippingquotes/getquote', 13, 'Quotes::get_quote'), ('/shippingquotes/watch', 17, 'Quotes::watch')},
        )
        self.assertTrue(all(r.protocol == Protocol.GRPC and r.methods == {'CALL'} for r in routes))

    def test_a_trait_named_by_its_full_path(self):
        routes = RustRepo({'src/main.rs': QUALIFIED}).extract().routes
        self.assertEqual([str(r.path) for r in routes], ['/ledger/postentry'])

    def test_other_traits_are_not_services(self):
        self.assertEqual(RustRepo({'src/lib.rs': NOT_TONIC}).extract().routes, [])

    def test_test_code_serves_nothing(self):
        self.assertEqual(RustRepo({'src/lib.rs': TESTED}).extract().routes, [])


if __name__ == '__main__':
    unittest.main()
