mod config;
mod sender;
mod stats;
mod statsd;

use std::thread;
use std::time::Instant;

use config::Config;
use sender::LineSender;
use stats::StatsReader;
use statsd::StatsdClient;

fn main() -> std::io::Result<()> {
    let config = Config::from_env();
    eprintln!("agent starting: collector={} statsd={}", config.collector_addr, config.statsd_addr);

    let reader = StatsReader::new(&config.hostname);
    let mut sender = LineSender::connect(&config.collector_addr)?;
    let statsd = StatsdClient::new(&config.statsd_addr, &config.metric_prefix)?;

    let mut tick: u32 = 0;
    loop {
        let started = Instant::now();
        let metrics = reader.read();

        if let Err(err) = sender.send_batch(&metrics) {
            eprintln!("send failed ({err}), reconnecting");
            statsd.incr("send_errors", 1)?;
            sender.reconnect()?;
            sender.send_batch(&metrics)?;
        }

        statsd.incr("samples_sent", metrics.len() as u64)?;
        statsd.timing("collect_ms", started.elapsed().as_secs_f64() * 1000.0)?;

        tick += 1;
        if config.iterations.is_some_and(|n| tick >= n) {
            break;
        }
        thread::sleep(config.interval);
    }

    eprintln!("agent done after {tick} ticks");
    Ok(())
}
