"""Manager for Trade Logic."""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from db.repositories.trade_repo import TradeRepository
from db.schemas import Trade, TradeLeg
from journal.calculator import (
    calculate_pnl, 
    calculate_holding_days, 
    determine_win_loss, 
    calculate_rr_actual,
    aggregate_partial_exists
)

logger = logging.getLogger(__name__)


class TradeManager:
    """Orchestrates trade operations."""

    def __init__(self, trade_repo: TradeRepository):
        self.repo = trade_repo

    def create_trade(self, data: Dict[str, Any]) -> str:
        """Create a new trade (Open)."""
        # Ensure calculated fields
        data["status"] = "open"
        data["qty_remaining"] = data["qty"]
        
        # Pydantic validation via Trade model
        trade = Trade(**data)
        return self.repo.insert_trade(trade)

    def close_trade(self, trade_id: str, exit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Close a trade completely.
        exit_data: {exit_price, exit_date, fees, emotion}
        """
        trade = self.repo.get_trade(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")
            
        if trade.status != "open":
            raise ValueError(f"Trade {trade_id} is not open")

        # Calculate Stats
        pnl = calculate_pnl(
            trade.entry_price, 
            exit_data["exit_price"], 
            trade.qty_remaining, # Close remaining
            exit_data.get("fees", 0)
        )
        
        holding_days = calculate_holding_days(trade.entry_date, exit_data["exit_date"])
        win_loss = determine_win_loss(pnl["pnl_rupiah"])
        
        # If there were previous legs, we need to aggregate them with this final close
        final_pnl_rupiah = pnl["pnl_rupiah"]
        final_pnl_percent = pnl["pnl_percent"] # This % is for this leg only?
        # If multi-leg, overall % calc is complex.
        # Let's verify if legs exist.
        
        weighted_exit = exit_data["exit_price"]
        
        if trade.legs:
            # Create a "virtual" leg for this final close to aggregate
            final_leg_dict = {
                "qty": trade.qty_remaining,
                "exit_price": exit_data["exit_price"],
                "fees": exit_data.get("fees", 0),
                "pnl_rupiah": pnl["pnl_rupiah"]
            }
            all_legs = [l.model_dump() for l in trade.legs] + [final_leg_dict]
            
            agg = aggregate_partial_exists(all_legs, trade.qty)
            final_pnl_rupiah = agg["total_pnl"]
            weighted_exit = agg["weighted_exit_price"]
            
            # Recalculate percent on total invested
            invested = trade.entry_price * trade.qty
            final_pnl_percent = (final_pnl_rupiah / invested) * 100 if invested > 0 else 0
            
            # Add this final leg to DB for completeness? 
            # Logic: close_trade implies finality. We can append leg OR just store final result.
            # Storing final leg is good for history.
            leg = TradeLeg(
                exit_date=exit_data["exit_date"],
                exit_price=exit_data["exit_price"],
                qty=trade.qty_remaining,
                fees=exit_data.get("fees", 0),
                pnl_rupiah=pnl["pnl_rupiah"],
                pnl_percent=pnl["pnl_percent"],
                emotion_tag=exit_data.get("emotion_tag")
            )
            self.repo.add_leg(trade_id, leg, 0)


        # Setup Entry SL for RR calc? Need SL to check RR.
        # We need to calculate Actual RR based on initial SL.
        # But we don't store SL in Trade model explicitly?
        # Wait, Trade model has no 'sl_price'. Logic gap?
        # US-9.1 says "Target strategy... Emotion...".
        # Implementation Plan schemas.py: Trade schema has `risk_percent` but not `sl_price`.
        # VCP/EMA strategies output SL.
        # If manual entry, user provides risk %, maybe not SL?
        # Actually US-9.1 example doesn't show SL input.
        # But for RR we need SL.
        # Let's assume we can't calc RR Actual if SL is missing.
        # Or add sl_price to Trade schema?
        # Sprint 3 Plan / Schemas: No sl_price.
        # SRS 3.2 says Risk Management...
        # Let's stick to strict schema. If no SL, RR is None.

        update_data = {
            "exit_date": exit_data["exit_date"],
            "exit_price": weighted_exit,
            "pnl_rupiah": final_pnl_rupiah,
            "pnl_percent": final_pnl_percent,
            "holding_days": holding_days,
            "win_loss": determine_win_loss(final_pnl_rupiah),
            "emotion_tag": exit_data.get("emotion_tag") # Final emotion overrides? Or append?
        }
        
        self.repo.close_trade(trade_id, update_data)
        return update_data

    def partial_close(self, trade_id: str, leg_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partial close a trade.
        leg_data: {exit_price, qty, fees, exit_date, emotion}
        """
        trade = self.repo.get_trade(trade_id)
        if not trade:
            raise ValueError("Trade not found")
            
        if leg_data["qty"] > trade.qty_remaining:
            raise ValueError(f"Partial qty {leg_data['qty']} > Remaining {trade.qty_remaining}")
            
        # Calc Leg P&L
        pnl = calculate_pnl(
            trade.entry_price,
            leg_data["exit_price"],
            leg_data["qty"],
            leg_data.get("fees", 0)
        )
        
        leg = TradeLeg(
            exit_date=leg_data["exit_date"],
            exit_price=leg_data["exit_price"],
            qty=leg_data["qty"],
            fees=leg_data.get("fees", 0),
            pnl_rupiah=pnl["pnl_rupiah"],
            pnl_percent=pnl["pnl_percent"],
            emotion_tag=leg_data.get("emotion_tag")
        )
        
        remaining = trade.qty_remaining - leg_data["qty"]
        self.repo.add_leg(trade_id, leg, remaining)
        
        # If remaining is 0, auto close?
        if remaining == 0:
            # We call close_trade logic but we just added the leg.
            # close_trade expects to add the final leg? 
            # My close_trade logic above handles "final leg".
            # If we used partial_close for the last bit, we need to mark closed.
            
            # Re-aggregate
            # trade.legs is stale (doesn't have the new one yet if we just added it to DB? 
            # wait, add_leg updates DB. trade object is old).
            
            # Simple approach: If remaining 0, trigger update to "closed" with aggregated stats.
            # We can reuse aggregation logic.
            
            # Fetch updated trade?
            trade = self.repo.get_trade(trade_id) # Reload
            legs = [l.model_dump() for l in trade.legs]
            agg = aggregate_partial_exists(legs, trade.qty)
            
            holding_days = calculate_holding_days(trade.entry_date, leg_data["exit_date"])
            
            update_data = {
                "exit_date": leg_data["exit_date"], # Latest exit date
                "exit_price": agg["weighted_exit_price"],
                "pnl_rupiah": agg["total_pnl"],
                "pnl_percent": (agg["total_pnl"] / (trade.entry_price * trade.qty)) * 100,
                "holding_days": holding_days,
                "win_loss": determine_win_loss(agg["total_pnl"]),
                "emotion_tag": leg_data.get("emotion_tag") # Last emotion
            }
            self.repo.close_trade(trade_id, update_data)
            return {**update_data, "status": "closed"}
            
        return {**leg.model_dump(), "status": "open", "remaining": remaining}
