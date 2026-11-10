use std::sync::Arc;
use std::time::Duration;

use futures::stream::{self, BoxStream, StreamExt};
use rskafka::client::consumer::{StartOffset, StreamConsumerBuilder};
use rskafka::client::partition::UnknownTopicHandling;
use rskafka::client::{Client, ClientBuilder};
use rskafka::record::RecordAndOffset;
use serde::Deserialize;

use crate::book::Book;

pub const SETTLED_TOPIC: &str = "payments.settled";
pub const REFUNDED_TOPIC: &str = "payments.refunded";

#[derive(Debug, Deserialize)]
struct PaymentEvent {
    payment_id: String,
    merchant_id: String,
    amount_cents: i64,
}

type TopicStream = BoxStream<'static, (&'static str, RecordAndOffset)>;

async fn subscribe(client: &Client, topic: &'static str) -> TopicStream {
    let partition = client
        .partition_client(topic, 0, UnknownTopicHandling::Retry)
        .await
        .expect("partition client");
    StreamConsumerBuilder::new(Arc::new(partition), StartOffset::Earliest)
        .with_max_wait_ms(200)
        .build()
        .filter_map(move |item| async move {
            match item {
                Ok((record, _high_watermark)) => Some((topic, record)),
                Err(err) => {
                    eprintln!("ledger kafka error on {topic}: {err}");
                    None
                }
            }
        })
        .boxed()
}

async fn connect(brokers: &str) -> Client {
    loop {
        match ClientBuilder::new(vec![brokers.to_string()]).build().await {
            Ok(client) => return client,
            Err(err) => {
                eprintln!("ledger waiting for kafka: {err}");
                tokio::time::sleep(Duration::from_millis(500)).await;
            }
        }
    }
}

pub async fn run(brokers: &str, book: Arc<Book>) {
    let client = connect(brokers).await;

    let settled = subscribe(&client, SETTLED_TOPIC).await;
    let refunded = subscribe(&client, REFUNDED_TOPIC).await;
    let mut events = stream::select(settled, refunded);

    while let Some((topic, record)) = events.next().await {
        let Some(value) = record.record.value else {
            continue;
        };
        let event: PaymentEvent = match serde_json::from_slice(&value) {
            Ok(event) => event,
            Err(err) => {
                eprintln!("ledger bad event on {topic}: {err}");
                continue;
            }
        };
        match topic {
            SETTLED_TOPIC => {
                book.credit(&event.merchant_id, event.amount_cents);
                println!("RECV L05 kafka {SETTLED_TOPIC} payment={}", event.payment_id);
            }
            REFUNDED_TOPIC => {
                book.debit(&event.merchant_id, event.amount_cents);
                println!("RECV L06 kafka {REFUNDED_TOPIC} payment={}", event.payment_id);
            }
            other => eprintln!("ledger ignoring topic {other}"),
        }
    }
}
