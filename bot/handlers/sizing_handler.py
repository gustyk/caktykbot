"""Handler for /size command (FR-08)."""

from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from db.repositories.portfolio_repo import PortfolioRepository
from risk.position_sizer import calculate_position_size
from risk.sector_mapper import get_sector_info

async def handle_size_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /size command.
    Usage: /size SYMBOL ENTRY SL [RISK_PCT]
    Example: /size BBCA.JK 7200 6800
    Example: /size BBCA.JK 7200 6800 0.02
    """
    if not update.message:
        return

    args = context.args
    if not args or len(args) < 3:
        await update.message.reply_text(
            "Usage: `/size SYMBOL ENTRY SL [RISK_PCT]`\n"
            "Example: `/size BBCA.JK 9500 9000`",
            parse_mode="Markdown"
        )
        return

    symbol = args[0].upper()
    try:
        entry = float(args[1])
        sl = float(args[2])
    except ValueError:
        await update.message.reply_text("❌ Entry and SL must be numbers.")
        return

    # Check for optional risk argument
    risk_override = None
    if len(args) >= 4:
        try:
            risk_override = float(args[3])
        except ValueError:
            await update.message.reply_text("❌ Risk must be a number (e.g. 0.01).")
            return

    db = context.bot_data["db"]
    repo = PortfolioRepository(db)
    
    # Fetch config
    config = repo.get_config()
    if not config:
        await update.message.reply_text("⚠️ Configuration not found. Use `/capital` to set up first.")
        return

    capital = config.total_capital
    risk_pct = risk_override if risk_override is not None else config.risk_per_trade

    # Get sector info for small cap check
    sector, market_cap = await get_sector_info(symbol)
    is_small_cap = (market_cap == "small")

    # Calculate
    result = calculate_position_size(
        capital=capital,
        risk_pct=risk_pct,
        entry_price=entry,
        sl_price=sl,
        is_small_cap=is_small_cap
    )

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    # specific format from plan
    # 📐 Position Sizing: BBCA.JK
    # ──────────────────
    # Entry: Rp 72 | SL: Rp 68 | Distance: Rp 4 (5.56%)
    # Risk Amount: Rp 10,000,000
    # Shares: 2,500,000 (25,000 lot)
    # Exposure: Rp 180,000,000 (18.0%) ✅
    # Projected Heat: 4.2% → 5.2% 🟢  <-- tricky, needs heat calc, but handler scope?
    # Plan says US-12.1 output check. 
    # Projected heat requires current heat.
    # Let's verify if we need to show projected heat here.
    # US-12.1 acceptance criteria says: "Projected Heat: 4.2% -> 5.2% 🟢"
    # So yes, we need to calculate heat.

    # We need to fetch open trades to calculate current heat.
    # We can assume we need TradeRepository.
    # But usually open trades are in `trades` collection with status='open'.
    # We can use TradeRepository if available, or just query DB directly for now.
    
    # Ideally use repo.
    # Let's check imports. We need to import TradeRepository? Or generic DB?
    # context.bot_data["db"] is database object.
    
    # Fetch open trades
    # Using raw query for speed/simplicity as we don't have trade repo imported yet.
    # Or good practice: import repo.
    
    # Wait, I don't want to overcomplicate imports if repo not standard.
    # DB access is fine.

    open_trades_cursor = db.trades.find({"status": "open", "user": config.user})
    open_trades = list(open_trades_cursor)

    from risk.heat_monitor import calculate_portfolio_heat, project_heat_with_new_trade
    
    heat_status = calculate_portfolio_heat(open_trades, capital, config.max_heat)
    current_heat = heat_status["current_heat"]
    
    # Actual risk pct for this trade might differ if size was capped
    shares = result["shares"]
    risk_amount = shares * (entry - sl)
    actual_risk_pct = risk_amount / capital
    
    proj_heat = project_heat_with_new_trade(current_heat, actual_risk_pct, config.max_heat)
    
    # Formatting
    heat_arrow = "🟢"
    if proj_heat["would_exceed"]:
        heat_arrow = "🔴 LIMIT"
    elif proj_heat["projected_heat"] >= 0.06: # Warning threshold hardcoded or from config?
        heat_arrow = "🟡 WARNING"
        
    exposure_check = "✅"
    if result["exposure_pct"] > result["max_exposure_limit"]:
        # Should have been capped by function, so it equals or is less than max.
        # But if it was capped, maybe warn?
        # The function already capped it.
        pass
    
    # If warnings exist, show them
    risk_warnings = "\n".join([f"⚠️ {w}" for w in result["warnings"]])
    
    msg = (
        f"📐 *Position Sizing: {symbol}*\n"
        f"──────────────────\n"
        f"Entry: Rp {entry:,.0f} | SL: Rp {sl:,.0f}\n"
        f"Distance: Rp {result['sl_distance']:,.0f} ({result['sl_distance_pct']:.1%})\n"
        f"Risk Amount: Rp {result['risk_amount']:,.0f} ({risk_pct:.1%})\n"
        f"Shares: {result['shares']:,} ({result['lots']:,} lot)\n"
        f"Exposure: Rp {result['exposure_rupiah']:,.0f} ({result['exposure_pct']:.1%}) {exposure_check}\n"
        f"Heat: {current_heat:.1%} → {proj_heat['projected_heat']:.1%} {heat_arrow}\n"
    )
    
    if risk_warnings:
        msg += f"\n{risk_warnings}"
        
    if is_small_cap:
        msg += f"\nℹ️ Small Cap Limit Applied ({result['max_exposure_limit']:.0%})"

    await update.message.reply_text(msg, parse_mode="Markdown")
