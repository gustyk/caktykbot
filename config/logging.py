"""Logging configuration for CakTykBot.

This module configures Loguru for environment-specific logging:
- Development: File-based logging with rotation
- Production: stdout logging for Railway
- Test: Minimal logging to avoid noise

Based on Phase 7 (Deployment Readiness) analysis.
"""

import sys
from pathlib import Path

from loguru import logger

from config.settings import settings


def setup_logging() -> None:
    """Configure logging based on environment.

    Development:
        - Logs to file: logs/caktykbot_{date}.log
        - Rotation: daily
        - Retention: 30 days
        - Level: from settings.LOG_LEVEL
        - Format: detailed with module/function/line
        - Backtrace: enabled
        - Diagnose: enabled

    Production:
        - Logs to stdout (Railway captures this)
        - Level: from settings.LOG_LEVEL
        - Format: structured without colors
        - Backtrace: enabled
        - Diagnose: disabled (security)

    Test:
        - Logs to stdout
        - Level: WARNING (reduce noise)
        - Format: minimal
    """
    # Remove default handler
    logger.remove()

    if settings.ENVIRONMENT == "development":
        # Development: File-based logging with rotation
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        logger.add(
            "logs/caktykbot_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level=settings.LOG_LEVEL,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{module}:{function}:{line} | "
                "{message}"
            ),
            backtrace=True,
            diagnose=True,
            enqueue=True,  # Thread-safe
        )

        # Also log to stdout for development convenience
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{module}</cyan>:<cyan>{function}</cyan> | "
                "{message}"
            ),
            colorize=True,
        )

        logger.info("Logging configured for DEVELOPMENT environment")

    elif settings.ENVIRONMENT == "production":
        # Production: stdout only (Railway log viewer)
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{module}:{function}:{line} | "
                "{message}"
            ),
            serialize=False,  # Plain text for Railway
            backtrace=True,
            diagnose=False,  # Don't expose sensitive data in production
            enqueue=True,  # Thread-safe
        )

        logger.info("Logging configured for PRODUCTION environment")

    elif settings.ENVIRONMENT == "test":
        # Test: Minimal logging to reduce noise
        logger.add(
            sys.stdout,
            level="WARNING",  # Only warnings and errors during tests
            format="{level: <8} | {message}",
            colorize=False,
        )

        logger.debug("Logging configured for TEST environment")

    else:
        # Fallback: stdout with INFO level
        logger.add(
            sys.stdout,
            level="INFO",
            format="{time:HH:mm:ss} | {level: <8} | {message}",
        )
        logger.warning(f"Unknown environment: {settings.ENVIRONMENT}, using fallback logging")


def get_logger():
    """Get configured logger instance.

    Returns:
        Loguru logger instance
    """
    return logger
