"""Handler for /signal command."""
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from db.repositories.signal_repo import SignalRepository


async def handle_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show daily signals."""
    try:
        db = context.bot_data["db"]
        repo = SignalRepository(db)
        
        # Get today's signals
        signals = repo.get_today_signals()
        
        if not signals:
            await update.message.reply_text(
                "⏳ Belum ada sinyal untuk hari ini.\n"
                "Pipeline mungkin belum berjalan atau tidak ada setup yang valid."
            )
            return

        # Format message
        date_str = datetime.now().strftime("%d %b %Y")
        lines = [f"📊 *CakTykBot Daily Signal — {date_str}*\n"]
        
        buy_signals = [s for s in signals if s.verdict == "BUY"]
        blocked_signals = [s for s in signals if s.risk_blocked or s.verdict in ["WAIT", "SUSPENDED"]]
        
        # Display BUY signals
        if buy_signals:
            lines.append("🟢 *BUY SIGNALS:*")
            lines.append("─────────────────")
            
            for i, sig in enumerate(buy_signals, 1):
                # Emoji confidence
                conf = "⭐⭐⭐" if sig.confidence == "High" else "⭐⭐" if sig.confidence == "Medium" else "⭐"
                
                lines.append(f"{i}. *{sig.symbol}* [{sig.strategy_source}]")
                lines.append(f"   Entry: {sig.entry_price:,.0f} | SL: {sig.sl_price:,.0f} | TP: {sig.tp_price:,.0f}")
                lines.append(f"   RR: 1:{sig.rr_ratio} | Conf: {sig.confidence} {conf}")
                
                # Risk Info (Sprint 4)
                if sig.lot_size:
                    lot = sig.lot_size
                    shares = lot * 100
                    exp = sig.exposure_pct * 100 if sig.exposure_pct else 0
                    lines.append(f"   📐 Size: {shares:,} shares ({lot:,} lot) | Exp: {exp:.1f}%")
                    
                if sig.heat_before is not None and sig.heat_after is not None:
                    heat_bef = sig.heat_before * 100
                    heat_aft = sig.heat_after * 100
                    
                    # Determine emoji based on heat
                    heat_emoji = "🟢"
                    # We might need config to know warning threshold, or hardcode generic
                    if heat_aft >= 6.0: # 6% warning
                        heat_emoji = "🟡 WARNING"
                    
                    lines.append(f"   🔥 Heat: {heat_bef:.1f}% → {heat_aft:.1f}% {heat_emoji}")
                
                lines.append("")
        else:
            if not blocked_signals:
                lines.append("⚪ *NO BUY SIGNALS*")
            
        # Display BLOCKED signals
        if blocked_signals:
            lines.append("⏸️ *BLOCKED SIGNALS:*")
            lines.append("─────────────────")
            start_num = len(buy_signals) + 1
            
            for i, sig in enumerate(blocked_signals, start_num):
                reason = sig.block_reason or "Risk Validation Failed"
                lines.append(f"{i}. *{sig.symbol}* [{sig.strategy_source}]")
                lines.append(f"   🔴 {reason}")
                lines.append("")

        lines.append("─────────────────")
        lines.append("_Disclaimer: Do your own research._")
        
        message = "\n".join(lines)
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in /signal handler: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan saat mengambil sinyal.")
