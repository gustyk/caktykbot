"""Tests for Sector Mapper."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from caktykbot.risk.sector_mapper import get_sector_info, check_sector_limit

class TestSectorMapper:
    
    @pytest.mark.asyncio
    async def test_get_sector_info_found(self):
        mock_db = MagicMock()
        mock_db.sector_map.find_one.return_value = {
            "sector": "Banking",
            "market_cap_category": "large"
        }
        
        sector, mcap = await get_sector_info("BBCA.JK", db=mock_db)
        assert sector == "Banking"
        assert mcap == "large"

    @pytest.mark.asyncio
    async def test_get_sector_info_not_found(self):
        mock_db = MagicMock()
        mock_db.sector_map.find_one.return_value = None
        
        sector, mcap = await get_sector_info("UNKNOWN", db=mock_db)
        assert sector == "Other"
        assert mcap == "small"

    @pytest.mark.asyncio
    async def test_check_sector_limit_allowed(self):
        mock_db = MagicMock()
        # Mock cursor for search_symbols query
        mock_cursor = MagicMock() # Sync cursor
        mock_cursor.__iter__.return_value = [
            {"symbol": "BBRI.JK", "sector": "Banking"},
            {"symbol": "TLKM.JK", "sector": "Telco"}
        ]
        mock_db.sector_map.find.return_value = mock_cursor
        
        # Open trades: 1 Banking, 1 Telco
        open_trades = [
            {"symbol": "BBRI.JK"}, # Sector Banking
            {"symbol": "TLKM.JK"}  # Sector Telco
        ]
        
        # New trade: BMRI.JK (Banking)
        
        res = await check_sector_limit("BMRI.JK", "Banking", open_trades, db=mock_db)
        
        assert res["allowed"]
        assert res["count"] == 1 # 1 existing banking stock

    @pytest.mark.asyncio
    async def test_check_sector_limit_reached(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = [
            {"symbol": "BBRI.JK", "sector": "Banking"},
            {"symbol": "BBNI.JK", "sector": "Banking"}
        ]
        mock_db.sector_map.find.return_value = mock_cursor
        
        open_trades = [
            {"symbol": "BBRI.JK"},
            {"symbol": "BBNI.JK"}
        ]
        
        res = await check_sector_limit("BMRI.JK", "Banking", open_trades, db=mock_db)
        
        assert not res["allowed"]
        assert res["count"] == 2
        assert "Sector limit" in res["message"]
