"""Notification domain.

Pure domain types and ports for the notification bounded context. No
framework, ORM or HTTP imports — those belong in :mod:`application` and
:mod:`infrastructure`. The ``test_neuro_ddd_boundaries`` suite enforces
that rule.
"""

from .types import Notification, NotificationType, OutboundNotification
from .ports import NotificationRepository, RealtimePusher

__all__ = [
    "Notification",
    "NotificationRepository",
    "NotificationType",
    "OutboundNotification",
    "RealtimePusher",
]
