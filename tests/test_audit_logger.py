
import pytest
from unittest.mock import MagicMock, patch
from monitoring.audit_logger import AuditLogger
from db.schemas import AuditLog

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def audit_logger_instance(mock_db):
    # Reset singleton
    AuditLogger._instance = None
    with patch("monitoring.audit_logger.get_database", return_value=mock_db):
        logger = AuditLogger()
        # Mock the repository to avoid DB calls
        logger.repo = MagicMock()
        return logger

def test_audit_logger_initialization(audit_logger_instance):
    assert audit_logger_instance._initialized is True
    assert audit_logger_instance.db is not None
    assert audit_logger_instance.repo is not None

def test_audit_logger_singleton():
    AuditLogger._instance = None
    with patch("monitoring.audit_logger.get_database") as mock_get_db:
        logger1 = AuditLogger()
        logger2 = AuditLogger()
        assert logger1 is logger2
        mock_get_db.assert_called_once()  # Should only initialize once

def test_log_success(audit_logger_instance):
    audit_logger_instance.log(
        event="TEST_EVENT",
        user="test_user",
        severity="INFO",
        details={"foo": "bar"},
        ip_address="127.0.0.1"
    )
    
    # Verify repo.log_event was called with correct data
    audit_logger_instance.repo.log_event.assert_called_once()
    call_args = audit_logger_instance.repo.log_event.call_args[0][0]
    
    assert isinstance(call_args, AuditLog)
    assert call_args.event == "TEST_EVENT"
    assert call_args.user == "test_user"
    assert call_args.severity == "INFO"
    assert call_args.details == {"foo": "bar"}
    assert call_args.ip_address == "127.0.0.1"

def test_log_failure_graceful_handling(audit_logger_instance):
    # Make repo raise an exception
    audit_logger_instance.repo.log_event.side_effect = Exception("DB Error")
    
    # Should not raise exception
    try:
        audit_logger_instance.log("TEST_EVENT", "test_user")
    except Exception:
        pytest.fail("AuditLogger.log raised exception on DB failure")
