import logging
from typing import Dict, Any
from datetime import datetime
import uuid
from pydantic import BaseModel, Field

class DashboardMetrics(BaseModel):
    total_events: int
    events_today: int

class AnalyticsService:
    """
    DEPRECATED: Use demon_engine.services.brain_engine.analytics.log_event for all analytics/telemetry.
    This class is retained for legacy dashboard metrics only. All new event tracking should use the privacy-safe DemonEngine telemetry pipeline.

    PII Posture:
    - Only hashes are stored for user identifiers.
    - Before/after code logging is opt-in and requires explicit user consent.
    - No raw PII or plaintext user data is written to analytics logs.
    """
    def __init__(self, db_instance: Any):
        self.logger = logging.getLogger(__name__)
        self.logger.warning("AnalyticsService is deprecated. Use DemonEngine telemetry for all new analytics.")
        if db_instance is None:
            raise ValueError("AnalyticsService requires a database instance.")
        self.db = db_instance
        self.EVENTS_COLLECTION = "analytics_events"
        self.logger.info("✅ AnalyticsService initialized (DEPRECATED).")

    async def track_event(self, event: Dict[str, Any]):
        self.logger.warning("track_event is deprecated. Use demon_engine.services.brain_engine.analytics.log_event instead.")
        # No direct Mongo writes. All analytics events must go through DemonEngine telemetry.
        return False

    async def generate_dashboard_metrics(self, user_id: str, date_range: int = 30) -> DashboardMetrics:
        # Legacy dashboard metrics only; consider migrating to log-based aggregation
        total_events = await self.db[self.EVENTS_COLLECTION].count_documents({"user_id": user_id})
        return DashboardMetrics(total_events=total_events, events_today=0)