"""Repository for managing backtest results."""
import logging
from typing import List, Optional, Dict
from datetime import datetime
from bson.objectid import ObjectId
from pymongo.database import Database
from pymongo import DESCENDING

from db.schemas import BacktestRun, BacktestTrade

logger = logging.getLogger(__name__)

class BacktestRepository:
    """Repository for Backtest runs and trades."""
    
    def __init__(self, db: Database):
        self.runs_collection = db.backtest_runs
        self.trades_collection = db.backtest_trades
        self._ensure_indexes()
        
    def _ensure_indexes(self):
        """Create indexes for backtest collections."""
        # Runs indexes
        self.runs_collection.create_index([("strategy", 1), ("created_at", -1)])
        
        # Trades indexes
        self.trades_collection.create_index([("run_id", 1), ("symbol", 1)])
        
    def create_run(self, run_data: BacktestRun) -> str:
        """Save a new backtest run."""
        data = run_data.model_dump(by_alias=True, exclude={"id"})
        result = self.runs_collection.insert_one(data)
        return str(result.inserted_id)
        
    def save_trades(self, trades: List[BacktestTrade]):
        """Save a batch of trades for a run."""
        if not trades:
            return
            
        data = [t.model_dump(by_alias=True, exclude={"id"}) for t in trades]
        self.trades_collection.insert_many(data)
        
    def get_last_run(self, strategy: str = None) -> Optional[BacktestRun]:
        """Get the most recent backtest run."""
        query = {}
        if strategy:
            query["strategy"] = strategy
            
        doc = self.runs_collection.find_one(query, sort=[("created_at", DESCENDING)])
        if doc:
            return BacktestRun(**doc)
        return None

    def get_run_by_id(self, run_id: str) -> Optional[BacktestRun]:
        """Get run by ID."""
        try:
            doc = self.runs_collection.find_one({"_id": ObjectId(run_id)})
            if doc:
                return BacktestRun(**doc)
        except Exception:
            return None
        return None

    def get_trades_by_run(self, run_id: str) -> List[BacktestTrade]:
        """Get all trades for a specific run."""
        cursor = self.trades_collection.find({"run_id": run_id})
        return [BacktestTrade(**doc) for doc in cursor]

    def get_all_runs(self) -> List[BacktestRun]:
        """Get all backtest runs history."""
        cursor = self.runs_collection.find().sort("created_at", DESCENDING)
        return [BacktestRun(**doc) for doc in cursor]
