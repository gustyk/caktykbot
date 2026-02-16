"""System health check module."""
import time
import requests
from datetime import datetime, timezone
from typing import Dict, Any

from db.connection import get_database
from db.repositories.pipeline_repo import PipelineRepository


def check_mongodb() -> Dict[str, Any]:
    """Check MongoDB connection."""
    start = time.time()
    try:
        db = get_database()
        # Ping
        db.command("ping")
        latency = (time.time() - start) * 1000
        return {"status": "ok", "latency_ms": round(latency, 2)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_yfinance() -> Dict[str, Any]:
    """Check external network connectivity to Yahoo Finance."""
    start = time.time()
    try:
        # Check basic connectivity to YFinance API (or Google/known host)
        # Using Google as proxy for internet connectivity since YF usage is via library
        requests.get("https://query1.finance.yahoo.com/v8/finance/chart/AAPL", timeout=5)
        latency = (time.time() - start) * 1000
        return {"status": "ok", "latency_ms": round(latency, 2)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_pipeline_status() -> Dict[str, Any]:
    """Check last pipeline run status."""
    try:
        db = get_database()
        repo = PipelineRepository(db)
        last_run = repo.get_latest_run()
        
        if not last_run:
            return {"status": "warning", "message": "No pipeline runs found"}
            
        now = datetime.now(timezone.utc)
        # Assuming run timestamp is timezone aware
        last_run_time = last_run.date
        if last_run_time.tzinfo is None:
             last_run_time = last_run_time.replace(tzinfo=timezone.utc)
             
        hours_since = (now - last_run_time).total_seconds() / 3600
        
        status = "ok"
        if hours_since > 25: # Should run daily
            status = "warning"
            
        return {
            "status": status,
            "last_run": last_run_time.isoformat(),
            "hours_since": round(hours_since, 1),
            "success_rate": f"{last_run.success_count}/{last_run.total_stocks}"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_all() -> Dict[str, Any]:
    """Run all health checks."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mongodb": check_mongodb(),
        "external_api": check_yfinance(),
        "pipeline": check_pipeline_status()
    }
