"""Repository for Portfolio Configuration."""
import logging
from typing import Optional

from pymongo.database import Database

from db.schemas import PortfolioConfig

logger = logging.getLogger(__name__)


class PortfolioRepository:
    """Repository for managing portfolio configuration in MongoDB."""

    def __init__(self, db: Database):
        self.collection = db.portfolio_config

    def get_config(self, user: str = "nesa") -> Optional[PortfolioConfig]:
        """Get portfolio config for a user."""
        doc = self.collection.find_one({"user": user})
        if doc:
            return PortfolioConfig(**doc)
        return None

    def upsert_config(self, config: PortfolioConfig) -> str:
        """Create or update portfolio config."""
        query = {"user": config.user}
        update = {
            "$set": config.model_dump(),
        }
        result = self.collection.update_one(query, update, upsert=True)
        return str(result.upserted_id or "updated")

    def update_capital(self, user: str, capital: float) -> bool:
        """Update just capital."""
        result = self.collection.update_one(
            {"user": user},
            {"$set": {"total_capital": capital}}
        )
        return result.modified_count > 0 or result.matched_count > 0

    def update_risk(self, user: str, risk: float) -> bool:
        """Update just risk per trade."""
        result = self.collection.update_one(
            {"user": user},
            {"$set": {"risk_per_trade": risk}}
        )
        return result.modified_count > 0 or result.matched_count > 0
