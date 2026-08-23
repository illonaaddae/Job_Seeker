"""Sending, following up, and reading what comes back."""

from .mailer import Mailer, SendResult, SendBlocked
from .followup import FollowupPlanner
from .inbox import InboxReader, classify_reply

__all__ = [
    "Mailer",
    "SendResult",
    "SendBlocked",
    "FollowupPlanner",
    "InboxReader",
    "classify_reply",
]
