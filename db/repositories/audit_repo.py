"""Repository for Audit Logs."""
from datetime import datetime, timezone
from typing import Optional

from pymongo.collection import Collection
from pymongo.database import Database

from db.schemas import AuditLog


class AuditRepository:
    """Repository for storing security audit logs in MongoDB."""

    def __init__(self, db: Database) -> None:
        """Initialize repository.

        Args:
            db: MongoDB database instance
        """
        self.collection: Collection = db.audit_logs

    def log_event(self, log: AuditLog) -> str:
        """Log a security event.

        Args:
            log: Audit log entry

        Returns:
            The inserted document ID
        """
        log_dict = log.model_dump()
        result = self.collection.insert_one(log_dict)
        return str(result.inserted_id)

    def get_logs(
        self, 
        user: Optional[str] = None, 
        event: Optional[str] = None,
        limit: int = 100
    ) -> list[AuditLog]:
        """Retrieve audit logs with filters.

        Args:
            user: Filter by username
            event: Filter by event type
            limit: Max records to return

        Returns:
            List of AuditLog entries
        """
        query = {}
        if user:
            query["user"] = user
        if event:
            query["event"] = event
            
        cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)
        return [AuditLog(**doc) for doc in cursor]
