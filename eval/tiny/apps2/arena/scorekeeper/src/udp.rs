use std::io;
use std::net::UdpSocket;

use crate::store::{RoundUpdate, ScoreStore};

/// Receives one JSON datagram per finished round and folds it into the store.
pub fn run_udp_listener(addr: &str, store: ScoreStore) -> io::Result<()> {
    let socket = UdpSocket::bind(addr)?;
    println!("scorekeeper udp listening on {addr}");
    let mut buf = [0u8; 8192];
    loop {
        let (len, peer) = socket.recv_from(&mut buf)?;
        match serde_json::from_slice::<RoundUpdate>(&buf[..len]) {
            Ok(update) => {
                println!(
                    "RECV U01 scorekeeper udp room={} round={} from={peer}",
                    update.room, update.round
                );
                store.apply(&update);
            }
            Err(err) => eprintln!("dropping malformed datagram from {peer}: {err}"),
        }
    }
}
