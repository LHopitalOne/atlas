mod http;
mod store;
mod udp;

use std::env;
use std::thread;

use store::ScoreStore;

fn main() {
    let udp_addr = env::var("SCOREKEEPER_UDP_ADDR").unwrap_or_else(|_| "127.0.0.1:44020".into());
    let http_addr = env::var("SCOREKEEPER_HTTP_ADDR").unwrap_or_else(|_| "127.0.0.1:44021".into());
    let store = ScoreStore::default();

    let udp_store = store.clone();
    thread::spawn(move || {
        if let Err(err) = udp::run_udp_listener(&udp_addr, udp_store) {
            eprintln!("udp listener stopped: {err}");
            std::process::exit(1);
        }
    });

    http::serve_http(&http_addr, store);
}
