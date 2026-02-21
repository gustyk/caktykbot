"""Sector Mapping and Verification (RR-005)."""

from typing import List, Dict, Tuple, Any
from loguru import logger

from db.connection import get_database
from db.schemas import SectorMap
from risk.constants import (
    MAX_STOCKS_PER_SECTOR,
    MSG_SECTOR_LIMIT
)

def get_sector_info(symbol: str, db=None) -> Tuple[str, str]:
    """
    Get sector and market cap category for a symbol.
    Returns (sector, market_cap_category).
    Default: ("Other", "small") if not found.
    """
    if db is None:
        db = get_database()
    
    # Try to find in sector_map collection
    mapping = db.sector_map.find_one({"symbol": symbol})
    
    if mapping:
        return mapping["sector"], mapping["market_cap_category"]
        
    return "Other", "small"


def check_sector_limit(
    symbol: str, 
    sector: str, 
    open_trades: List[Dict],
    db=None
) -> Dict[str, Any]:
    """
    Check if adding a new trade would exceed the sector limit.
    
    Args:
        symbol: Symbol to check
        sector: Sector of the symbol
        open_trades: List of currently open trades (dicts)
        db: Optional database instance
        
    Returns:
        Dict with 'allowed' (bool) and 'message' (str)
    """
    # Count open trades in the same sector
    # Exclude the symbol itself if it's already open (e.g. adding to position)
    # But usually we check for new signals.
    
    # We need to look up sectors for open trades as well, 
    # since trade record might not have sector info stored directly 
    # (unless we denormalize it).
    # Ideally, we should fetch sectors for all open trades.
    # For performance, we can do it here or assume sector is passed in trade.
    # Let's assume we fetch it here.
    
    if db is None:
        db = get_database()
        
    sector_counts = {}
    
    # Get all symbols from open trades
    search_symbols = [t["symbol"] for t in open_trades if t["symbol"] != symbol]
    
    if not search_symbols:
        return {"allowed": True, "count": 0, "max": MAX_STOCKS_PER_SECTOR, "message": ""}
        
    # Fetch all sectors in one go
    cursor = db.sector_map.find({"symbol": {"$in": search_symbols}})
    # PyMongo sync
    mappings = {doc["symbol"]: doc["sector"] for doc in cursor}
    
    current_count = 0
    for trade in open_trades:
        tsym = trade["symbol"]
        if tsym == symbol:
            continue
            
        tsector = mappings.get(tsym, "Other")
        if tsector == sector and sector != "Other": # Don't limit "Other" sector? Or do we?
             # Usually "Other" might be a catch-all, but let's count it too to be safe/strict, 
             # OR maybe "Other" is safe. Let's strict for now.
             current_count += 1
             
    if current_count >= MAX_STOCKS_PER_SECTOR:
        return {
            "allowed": False,
            "count": current_count,
            "max": MAX_STOCKS_PER_SECTOR,
            "message": MSG_SECTOR_LIMIT.format(count=current_count, sector=sector)
        }
        
    return {
        "allowed": True, 
        "count": current_count, 
        "max": MAX_STOCKS_PER_SECTOR,
        "message": ""
    }
