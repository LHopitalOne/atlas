import logging
import uuid
from collections import Counter

from app import rules
from app.pb import moderation_pb2, moderation_pb2_grpc

log = logging.getLogger(__name__)


class ModerationService(moderation_pb2_grpc.ModerationServicer):
    def __init__(self) -> None:
        self._reports: Counter[str] = Counter()

    def CheckMessage(self, request, context):
        verdict = rules.evaluate(request.text)
        if not verdict.allowed:
            log.info("rejected message from %s in %s: %s", request.author, request.room_id, verdict.reason)
        return moderation_pb2.CheckMessageResponse(
            allowed=verdict.allowed,
            reason=verdict.reason,
            sanitized_text=verdict.sanitized_text,
        )

    def ReportUser(self, request, context):
        self._reports[request.reported] += 1
        ticket_id = uuid.uuid4().hex[:12]
        log.info("report %s: %s reported %s (%s)", ticket_id, request.reporter, request.reported, request.reason)
        return moderation_pb2.ReportUserResponse(ticket_id=ticket_id, open_reports=self._reports[request.reported])
