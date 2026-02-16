"""Seed script for Sector Map (Top 20 Watchlist)."""

import asyncio
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.getcwd())

from db.connection import get_db
from db.schemas import SectorMap, MarketCapCategory
from loguru import logger

SECTOR_DATA = [
    {"symbol": "BBCA.JK", "sector": "Finance", "market_cap": "large"},
    {"symbol": "BBRI.JK", "sector": "Finance", "market_cap": "large"},
    {"symbol": "BMRI.JK", "sector": "Finance", "market_cap": "large"},
    {"symbol": "BBNI.JK", "sector": "Finance", "market_cap": "large"},
    {"symbol": "TLKM.JK", "sector": "Infrastructure", "market_cap": "large"},
    {"symbol": "ASII.JK", "sector": "Conglomerate", "market_cap": "large"},
    {"symbol": "ICBP.JK", "sector": "Consumer Non-Cyclicals", "market_cap": "large"},
    {"symbol": "UNVR.JK", "sector": "Consumer Non-Cyclicals", "market_cap": "large"},
    {"symbol": "ADRO.JK", "sector": "Energy", "market_cap": "large"},
    {"symbol": "PTBA.JK", "sector": "Energy", "market_cap": "mid"},
    {"symbol": "PGAS.JK", "sector": "Energy", "market_cap": "mid"},
    {"symbol": "ANTM.JK", "sector": "Basic Materials", "market_cap": "large"},
    {"symbol": "INCO.JK", "sector": "Basic Materials", "market_cap": "mid"},
    {"symbol": "TINS.JK", "sector": "Basic Materials", "market_cap": "mid"},
    {"symbol": "UNTR.JK", "sector": "Industrials", "market_cap": "large"},
    {"symbol": "GOTO.JK", "sector": "Technology", "market_cap": "large"},
    {"symbol": "EMTK.JK", "sector": "Technology", "market_cap": "large"},
    {"symbol": "MDKA.JK", "sector": "Basic Materials", "market_cap": "large"},
    {"symbol": "INKP.JK", "sector": "Basic Materials", "market_cap": "large"},
    {"symbol": "CPIN.JK", "sector": "Consumer Non-Cyclicals", "market_cap": "large"},
]

async def seed_sectors():
    """Seed sector_map collection."""
    db = await get_db()
    collection = db.sector_map
    
    logger.info(f"Seeding {len(SECTOR_DATA)} sectors...")
    
    for item in SECTOR_DATA:
        sector_map = SectorMap(
            symbol=item["symbol"],
            sector=item["sector"],
            market_cap_category=MarketCapCategory(item["market_cap"]),
            updated_at=datetime.now(timezone.utc)
        )
        
        await collection.update_one(
            {"symbol": item["symbol"]},
            {"$set": sector_map.model_dump()},
            upsert=True
        )
        logger.info(f"Seeded: {item['symbol']} -> {item['sector']}")
        
    logger.info("Seeding complete.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed_sectors())
