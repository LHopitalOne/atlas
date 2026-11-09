import os

GRPC_HOST = os.getenv("MODERATION_HOST", "127.0.0.1")
GRPC_PORT = int(os.getenv("MODERATION_GRPC_PORT", "41311"))
MAX_WORKERS = int(os.getenv("MODERATION_WORKERS", "4"))
MAX_MESSAGE_LENGTH = int(os.getenv("MODERATION_MAX_LENGTH", "500"))
BLOCKED_TERMS = tuple(
    term.strip().lower()
    for term in os.getenv("MODERATION_BLOCKED_TERMS", "crypto giveaway,free money,click here").split(",")
    if term.strip()
)
MASKED_WORDS = ("darn", "heck")
