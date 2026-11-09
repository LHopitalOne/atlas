from unittest import mock

import pytest

from ledger_sdk import InsufficientFunds, LedgerClient


def _response(status, payload):
    resp = mock.Mock()
    resp.status_code = status
    resp.json.return_value = payload
    return resp


def test_create_transfer_posts_to_transfers():
    session = mock.Mock(headers={})
    session.request.return_value = _response(
        201, {"id": 7, "source_id": 1, "destination_id": 2, "amount": 500, "reference": "inv-1"}
    )
    client = LedgerClient("http://ledger.test/", session=session)

    transfer = client.create_transfer(1, 2, 500, reference="inv-1")

    assert transfer.id == 7
    method, url = session.request.call_args.args
    assert (method, url) == ("POST", "http://ledger.test/transfers")


def test_insufficient_funds_maps_to_exception():
    session = mock.Mock(headers={})
    session.request.return_value = _response(
        422, {"error": "insufficient_funds", "message": "nope"}
    )
    client = LedgerClient("http://ledger.test", session=session)

    with pytest.raises(InsufficientFunds):
        client.create_transfer(1, 2, 500)
