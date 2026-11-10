use std::collections::HashMap;
use std::sync::Mutex;

use serde::Serialize;

#[derive(Clone, Debug, Default, Serialize)]
pub struct Balance {
    pub merchant_id: String,
    pub settled_cents: i64,
    pub refunded_cents: i64,
    pub balance_cents: i64,
}

#[derive(Default)]
pub struct Book {
    balances: Mutex<HashMap<String, Balance>>,
}

impl Book {
    pub fn credit(&self, merchant_id: &str, amount_cents: i64) {
        self.apply(merchant_id, |b| b.settled_cents += amount_cents);
    }

    pub fn debit(&self, merchant_id: &str, amount_cents: i64) {
        self.apply(merchant_id, |b| b.refunded_cents += amount_cents);
    }

    pub fn get(&self, merchant_id: &str) -> Balance {
        let balances = self.balances.lock().expect("book lock");
        balances.get(merchant_id).cloned().unwrap_or_else(|| Balance {
            merchant_id: merchant_id.to_string(),
            ..Balance::default()
        })
    }

    fn apply(&self, merchant_id: &str, change: impl FnOnce(&mut Balance)) {
        let mut balances = self.balances.lock().expect("book lock");
        let entry = balances
            .entry(merchant_id.to_string())
            .or_insert_with(|| Balance {
                merchant_id: merchant_id.to_string(),
                ..Balance::default()
            });
        change(entry);
        entry.balance_cents = entry.settled_cents - entry.refunded_cents;
    }
}
