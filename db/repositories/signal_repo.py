"""Signal repository for MongoDB."""
from datetime import datetime, timezone
from typing import List, Optional

from pymongo.collection import Collection
from pymongo.database import Database

from db.schemas import SignalInDB
from engine.signal_generator import FinalSignal


class SignalRepository:
    """Repository for managing trading signals."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.collection: Collection = db.signals

    def upsert_signal(self, signal: FinalSignal) -> str:
        """
        Upsert a signal into the database.
        Unique on symbol + date.
        """
        # Convert FinalSignal dataclass to SignalInDB model (pydantic handles validation)
        # We need to ensure date is datetime object
        
        signal_db = SignalInDB(
            symbol=signal.symbol,
            date=signal.date,
            verdict=signal.verdict,
            strategy_source=signal.strategy_source,
            strategy_sources=signal.strategy_sources,
            entry_price=signal.entry_price,
            sl_price=signal.sl_price,
            tp_price=signal.tp_price,
            rr_ratio=signal.rr_ratio,
            tech_score=signal.tech_score,
            confidence=signal.confidence,
            reasoning=signal.reasoning
        )
        
        query = {
            "symbol": signal_db.symbol,
            "date": signal_db.date
        }
        
        update = {
            "$set": signal_db.model_dump(exclude={"created_at"}),
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
        }
        
        result = self.collection.update_one(query, update, upsert=True)
        return str(result.upserted_id or "updated")

    def get_today_signals(self, verdict_filter: Optional[str] = None) -> List[SignalInDB]:
        """
        Get all signals for today (UTC date).
        Currently relies on 'date' field being strict midnight UTC.
        """
        # Determine 'today' based on server time or just use latest date in DB?
        # Ideally we query for a specific date range (today's date).
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        query = {"date": now}
        if verdict_filter:
            query["verdict"] = verdict_filter
            
        cursor = self.collection.find(query).sort("tech_score", -1)
        return [SignalInDB(**doc) for doc in cursor]

    def get_signal_by_symbol(self, symbol: str, limit: int = 7) -> List[SignalInDB]:
        """Get latest signals for a symbol."""
        cursor = self.collection.find({"symbol": symbol}).sort("date", -1).limit(limit)
        return [SignalInDB(**doc) for doc in cursor]
