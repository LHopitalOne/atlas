import unittest

from atlas_bridge.core.http import Protocol

from .support import RustRepo

R = Protocol.REDIS
SOURCE = """
use redis::AsyncCommands;
use redis::aio::MultiplexedConnection;

const DONE: &str = "jobs:done";

struct Worker {
    queue: String,
    events: MultiplexedConnection,
}

impl Worker {
    async fn finish(&mut self, id: &str) {
        let _: i64 = self.events.publish(DONE, id).await.unwrap();
    }
}

async fn run(queue: String) -> redis::RedisResult<()> {
    let client = redis::Client::open("redis://127.0.0.1/")?;
    let mut conn = client.get_multiplexed_async_connection().await?;
    let events = client.get_multiplexed_async_connection().await?;
    let mut worker = Worker { queue, events };
    let _: Option<(String, String)> = conn.brpop("jobs:pending", 5.0).await?;
    let _: i64 = conn.lpush("jobs:retry", "1").await?;
    worker.finish("1").await;
    Ok(())
}
"""


class RedisTest(unittest.TestCase):
    def test_commands_on_connections_a_client_makes(self):
        ex = RustRepo({'src/main.rs': SOURCE}).extract()
        self.assertEqual({(c.protocol, str(c.path)) for c in ex.calls}, {(R, '/jobs:done'), (R, '/jobs:retry')})
        self.assertEqual({(r.protocol, str(r.path)) for r in ex.routes}, {(R, '/jobs:pending')})


if __name__ == '__main__':
    unittest.main()
