use std::io::{self, BufWriter, Write};
use std::net::TcpStream;
use std::time::Duration;

use crate::stats::Metric;

pub struct LineSender {
    addr: String,
    writer: BufWriter<TcpStream>,
}

impl LineSender {
    pub fn connect(addr: &str) -> io::Result<Self> {
        let stream = TcpStream::connect(addr)?;
        stream.set_nodelay(true)?;
        stream.set_write_timeout(Some(Duration::from_secs(5)))?;
        Ok(LineSender { addr: addr.to_string(), writer: BufWriter::new(stream) })
    }

    pub fn send_batch(&mut self, metrics: &[Metric]) -> io::Result<()> {
        for m in metrics {
            writeln!(self.writer, "{}", m.to_line())?;
        }
        self.writer.flush()
    }

    pub fn reconnect(&mut self) -> io::Result<()> {
        *self = LineSender::connect(&self.addr)?;
        Ok(())
    }
}
