use std::os::raw::{c_double, c_int};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

extern "C" {
    fn getloadavg(loadavg: *mut c_double, nelem: c_int) -> c_int;
}

#[derive(Debug, Clone)]
pub struct Metric {
    pub name: String,
    pub value: f64,
    pub timestamp: u64,
    pub host: String,
}

impl Metric {
    pub fn to_line(&self) -> String {
        format!("{} {} {} host={}", self.name, self.value, self.timestamp, self.host)
    }
}

pub struct StatsReader {
    started: Instant,
    host: String,
}

impl StatsReader {
    pub fn new(host: &str) -> Self {
        StatsReader { started: Instant::now(), host: host.to_string() }
    }

    fn load_average() -> Option<[f64; 3]> {
        let mut loads = [0.0f64; 3];
        let n = unsafe { getloadavg(loads.as_mut_ptr(), 3) };
        (n == 3).then_some(loads)
    }

    pub fn read(&self) -> Vec<Metric> {
        let ts = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
        let metric = |name: &str, value: f64| Metric {
            name: name.to_string(),
            value,
            timestamp: ts,
            host: self.host.clone(),
        };

        let mut out = Vec::new();
        if let Some([l1, l5, l15]) = Self::load_average() {
            out.push(metric("system.load.1", l1));
            out.push(metric("system.load.5", l5));
            out.push(metric("system.load.15", l15));
        }
        let cpus = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(1);
        out.push(metric("system.cpus", cpus as f64));
        out.push(metric("agent.uptime_seconds", self.started.elapsed().as_secs_f64()));
        out
    }
}
