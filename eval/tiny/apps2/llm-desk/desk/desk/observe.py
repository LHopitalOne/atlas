import logging
import sys

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(message)s"))

recv_log = logging.getLogger("desk.recv")
recv_log.addHandler(_handler)
recv_log.setLevel(logging.INFO)
recv_log.propagate = False


def recv(link_id: str, detail: str) -> None:
    recv_log.info("RECV %s %s", link_id, detail)
