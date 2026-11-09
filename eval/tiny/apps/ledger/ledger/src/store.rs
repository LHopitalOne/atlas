use std::collections::HashMap;
use std::sync::Mutex;

use serde::Serialize;

use crate::error::LedgerError;

#[derive(Clone, Serialize)]
pub struct Account {
    pub id: u64,
    pub name: String,
    pub currency: String,
    pub allow_overdraft: bool,
    pub balance: i64,
}

#[derive(Clone, Serialize)]
pub struct Transfer {
    pub id: u64,
    pub source_id: u64,
    pub destination_id: u64,
    pub amount: i64,
    pub reference: String,
}

#[derive(Default)]
struct Inner {
    accounts: HashMap<u64, Account>,
    transfers: Vec<Transfer>,
    next_id: u64,
}

pub struct Store {
    default_currency: String,
    inner: Mutex<Inner>,
}

impl Store {
    pub fn new(default_currency: String) -> Self {
        Self { default_currency, inner: Mutex::new(Inner::default()) }
    }

    pub fn open_account(&self, name: String, currency: Option<String>, allow_overdraft: bool) -> Account {
        let mut inner = self.inner.lock().unwrap();
        inner.next_id += 1;
        let account = Account {
            id: inner.next_id,
            name,
            currency: currency.unwrap_or_else(|| self.default_currency.clone()),
            allow_overdraft,
            balance: 0,
        };
        inner.accounts.insert(account.id, account.clone());
        account
    }

    pub fn account(&self, id: u64) -> Result<Account, LedgerError> {
        let inner = self.inner.lock().unwrap();
        inner.accounts.get(&id).cloned().ok_or(LedgerError::AccountNotFound(id))
    }

    pub fn transfers_for(&self, id: u64) -> Result<Vec<Transfer>, LedgerError> {
        let inner = self.inner.lock().unwrap();
        if !inner.accounts.contains_key(&id) {
            return Err(LedgerError::AccountNotFound(id));
        }
        Ok(inner
            .transfers
            .iter()
            .filter(|t| t.source_id == id || t.destination_id == id)
            .cloned()
            .collect())
    }

    pub fn post_transfer(
        &self,
        source_id: u64,
        destination_id: u64,
        amount: i64,
        reference: String,
    ) -> Result<Transfer, LedgerError> {
        if amount <= 0 {
            return Err(LedgerError::InvalidAmount);
        }
        let mut inner = self.inner.lock().unwrap();
        let source = inner.accounts.get(&source_id).cloned().ok_or(LedgerError::AccountNotFound(source_id))?;
        let destination =
            inner.accounts.get(&destination_id).cloned().ok_or(LedgerError::AccountNotFound(destination_id))?;
        if source.currency != destination.currency {
            return Err(LedgerError::CurrencyMismatch);
        }
        if !source.allow_overdraft && source.balance < amount {
            return Err(LedgerError::InsufficientFunds { account_id: source_id, balance: source.balance, amount });
        }

        inner.accounts.get_mut(&source_id).unwrap().balance -= amount;
        inner.accounts.get_mut(&destination_id).unwrap().balance += amount;
        inner.next_id += 1;
        let transfer = Transfer { id: inner.next_id, source_id, destination_id, amount, reference };
        inner.transfers.push(transfer.clone());
        Ok(transfer)
    }
}
