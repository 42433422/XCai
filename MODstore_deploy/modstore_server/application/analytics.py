"""Analytics application service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from modstore_server.domain.analytics import AnalyticsDashboard
from modstore_server.infrastructure.analytics_repository import AnalyticsRepository


class AnalyticsApplicationService:
    def __init__(self, db: Session):
        self.repository = AnalyticsRepository(db)

    def dashboard_for_user(self, user_id: int) -> AnalyticsDashboard:
        return self.repository.dashboard_for_user(user_id)
