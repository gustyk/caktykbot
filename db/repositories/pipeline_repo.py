"""Pipeline repository for MongoDB.

This module implements the repository pattern for tracking pipeline execution history.
"""

from datetime import datetime
from typing import List, Optional

from pymongo.collection import Collection
from pymongo.database import Database

from db.schemas import PipelineRun
from utils.exceptions import DuplicatePipelineRunError


class PipelineRepository:
    """Repository for managing pipeline run history in MongoDB."""

    def __init__(self, db: Database) -> None:
        """Initialize repository.

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection: Collection = db.pipeline_runs

    def record_run(self, run_data: PipelineRun) -> PipelineRun:
        """Record a pipeline execution run.

        Prevents duplicate runs for the same date (midnight).

        Args:
            run_data: Pipeline run data

        Returns:
            The recorded run data

        Raises:
            DuplicatePipelineRunError: If a run already exists for this date
        """
        # Check if already exists for this exact datetime
        if self.collection.find_one({"date": run_data.date}):
            raise DuplicatePipelineRunError(
                f"Pipeline run for {run_data.date} already recorded"
            )

        run_dict = run_data.model_dump()
        self.collection.insert_one(run_dict)
        return run_data

    def get_latest_run(self) -> Optional[PipelineRun]:
        """Get the most recent successful pipeline run.

        Returns:
            PipelineRun instance or None
        """
        doc = self.collection.find_one(sort=[("date", -1)])
        if not doc:
            return None
        return PipelineRun(**doc)

    def get_history(self, limit: int = 10) -> List[PipelineRun]:
        """Get recent pipeline run history.

        Args:
            limit: Number of records to return

        Returns:
            List of PipelineRun instances
        """
        cursor = self.collection.find().sort("date", -1).limit(limit)
        return [PipelineRun(**doc) for doc in cursor]
