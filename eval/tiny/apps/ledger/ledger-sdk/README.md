# ledger-sdk

Python client for the Ledger API.

```python
from ledger_sdk import LedgerClient

client = LedgerClient("http://127.0.0.1:41410")
acct = client.create_account("acme", allow_overdraft=True)
client.create_transfer(acct.id, other.id, 1999, reference="inv-42")
```
