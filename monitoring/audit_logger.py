"""Audit logger for security events."""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger as app_logger

from db.connection import get_database
from db.repositories.audit_repo import AuditRepository
from db.schemas import AuditLog


class AuditLogger:
    """Centralized audit logging service."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuditLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.db = get_database()
        self.repo = AuditRepository(self.db)
        self._initialized = True
        
    def log(
        self, 
        event: str, 
        user: str, 
        severity: str = "INFO", 
        details: Optional[dict] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Record a security event.
        
        Args:
            event: Name of the event (e.g., "LOGIN_SUCCESS", "CONFIG_CHANGE")
            user: Username responsible for the action
            severity: INFO, WARNING, or CRITICAL
            details: Additional context
            ip_address: IP address of the user (if applicable)
        """
        try:
            log_entry = AuditLog(
                event=event,
                user=user,
                severity=severity,
                details=details or {},
                ip_address=ip_address,
                timestamp=datetime.now(timezone.utc)
            )
            
            # 1. Log to Database
            self.repo.log_event(log_entry)
            
            # 2. Log to Application Logs
            log_msg = f"AUDIT | {event} | User: {user} | {severity}"
            if severity == "CRITICAL":
                app_logger.critical(log_msg)
            elif severity == "WARNING":
                app_logger.warning(log_msg)
            else:
                app_logger.info(log_msg)
                
        except Exception as e:
            # Fallback if DB logging fails - never crash the app
            app_logger.error(f"Failed to write audit log: {e}")

# Global instance
audit_logger = AuditLogger()
