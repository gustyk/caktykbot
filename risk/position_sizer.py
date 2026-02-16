"""Position Sizing Logic (FR-08)."""

from typing import Dict, Any

from loguru import logger

from caktykbot.risk.constants import (
    MAX_EXPOSURE_PER_STOCK,
    MAX_SMALL_CAP_EXPOSURE,
    MSG_SL_TOO_WIDE,
    MSG_EXPOSURE_LIMIT,
)


def calculate_position_size(
    capital: float,
    risk_pct: float,
    entry_price: float,
    sl_price: float,
    is_small_cap: bool = False
) -> Dict[str, Any]:
    """
    Calculate position size based on risk and capital.
    
    Args:
        capital: Total trading capital
        risk_pct: Risk per trade (decimal, e.g. 0.01)
        entry_price: Entry price per share
        sl_price: Stop loss price per share
        is_small_cap: Whether the stock is small cap
        
    Returns:
        Dict containing sizing details and warnings
    """
    if capital <= 0:
        return {"error": "Capital must be > 0"}
    
    if entry_price <= 0 or sl_price <= 0:
        return {"error": "Prices must be > 0"}
        
    if sl_price >= entry_price:
        return {"error": "SL must be below Entry for Long positions"}
        
    # 1. Calculate Risk Amount
    risk_amount = capital * risk_pct
    
    # 2. Calculate Stop Loss Distance
    sl_distance = entry_price - sl_price
    sl_distance_pct = sl_distance / entry_price
    
    # Validation: SL too wide (> 15%)
    warnings = []
    if sl_distance_pct > 0.15:
        warnings.append(MSG_SL_TOO_WIDE.format(distance=sl_distance_pct))
        
    # 3. Calculate Shares (Risk / Distance)
    # Avoid division by zero (though checks above prevent it)
    raw_shares = int(risk_amount / sl_distance)
    
    # Round down to nearest lot (100 shares)
    lots = raw_shares // 100
    shares = lots * 100
    
    # 4. Exposure Check
    exposure_rupiah = shares * entry_price
    exposure_pct = exposure_rupiah / capital
    
    # Determine Max Exposure
    max_exposure_limit = MAX_SMALL_CAP_EXPOSURE if is_small_cap else MAX_EXPOSURE_PER_STOCK
    
    # Cap size if exposure exceeds limit
    if exposure_pct > max_exposure_limit:
        max_allowed_rupiah = capital * max_exposure_limit
        max_allowed_shares = int(max_allowed_rupiah / entry_price)
        
        # Recalculate based on cap
        lots = max_allowed_shares // 100
        shares = lots * 100
        exposure_rupiah = shares * entry_price
        exposure_pct = exposure_rupiah / capital
        
        warnings.append(MSG_EXPOSURE_LIMIT.format(
            exposure=exposure_pct, 
            limit=max_exposure_limit
        ))
        
    return {
        "risk_amount": risk_amount,
        "sl_distance": sl_distance,
        "sl_distance_pct": sl_distance_pct,
        "shares": shares,
        "lots": lots,
        "exposure_rupiah": exposure_rupiah,
        "exposure_pct": exposure_pct,
        "warnings": warnings,
        "max_exposure_limit": max_exposure_limit,
        "is_small_cap": is_small_cap
    }


def adjust_for_small_cap(
    base_result: Dict[str, Any], 
    avg_volume: int, 
    market_cap_category: str
) -> Dict[str, Any]:
    """
    Adjust position size for small cap stocks.
    
    Note: Logic is now integrated into calculate_position_size via is_small_cap flag,
    but this function can serve as a helper to determine that flag or apply 
    additional adjustments if needed separately.
    """
    # This might be redundant if we pass is_small_cap to main function,
    # keeping it for now as per plan structure or future extension.
    return base_result
