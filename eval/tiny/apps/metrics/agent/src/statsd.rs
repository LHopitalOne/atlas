use std::io;
use std::net::UdpSocket;

pub struct StatsdClient {
    socket: UdpSocket,
    target: String,
    prefix: String,
}

impl StatsdClient {
    pub fn new(target: &str, prefix: &str) -> io::Result<Self> {
        let socket = UdpSocket::bind("0.0.0.0:0")?;
        Ok(StatsdClient { socket, target: target.to_string(), prefix: prefix.to_string() })
    }

    pub fn incr(&self, name: &str, by: u64) -> io::Result<()> {
        self.send(&format!("{}.{}:{}|c", self.prefix, name, by))
    }

    pub fn timing(&self, name: &str, ms: f64) -> io::Result<()> {
        self.send(&format!("{}.{}:{:.3}|ms", self.prefix, name, ms))
    }

    fn send(&self, payload: &str) -> io::Result<()> {
        self.socket.send_to(payload.as_bytes(), &self.target)?;
        Ok(())
    }
}
