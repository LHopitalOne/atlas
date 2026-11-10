use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use serde::{Deserialize, Serialize};

/// One datagram from the game-server: per-player points earned in a round.
#[derive(Debug, Deserialize)]
pub struct RoundUpdate {
    pub room: String,
    pub round: u32,
    pub scores: HashMap<String, i64>,
}

#[derive(Debug, Serialize)]
pub struct ScoreEntry {
    pub player: String,
    pub points: i64,
}

#[derive(Clone, Default)]
pub struct ScoreStore {
    totals: Arc<Mutex<HashMap<String, i64>>>,
}

impl ScoreStore {
    pub fn apply(&self, update: &RoundUpdate) {
        let mut totals = self.totals.lock().expect("score store poisoned");
        for (player, points) in &update.scores {
            *totals.entry(player.clone()).or_insert(0) += points;
        }
    }

    pub fn snapshot(&self) -> Vec<ScoreEntry> {
        let totals = self.totals.lock().expect("score store poisoned");
        let mut entries: Vec<ScoreEntry> = totals
            .iter()
            .map(|(player, points)| ScoreEntry { player: player.clone(), points: *points })
            .collect();
        entries.sort_by(|a, b| b.points.cmp(&a.points).then_with(|| a.player.cmp(&b.player)));
        entries
    }
}
