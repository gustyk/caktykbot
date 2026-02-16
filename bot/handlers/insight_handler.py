from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from db.repositories.trade_repo import TradeRepository
from analytics.monthly_report import generate_monthly_report
from analytics.bias_detector import detect_biases
from analytics.adaptive_scorer import calculate_strategy_scores

async def handle_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /report command. Usage: /report [MM] [YYYY]"""
    db = context.bot_data["db"]
    repo = TradeRepository(db)
    
    # Defaults
    now = datetime.now()
    month = now.month
    year = now.year
    
    # Parse args
    if context.args:
        try:
            if len(context.args) >= 1:
                month = int(context.args[0])
            if len(context.args) >= 2:
                year = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Use: `/report [MM] [YYYY]`")
            return

    trades = repo.get_all_closed_trades()
    # Convert to dicts
    trade_dicts = [t.model_dump() for t in trades]
    
    report_md = generate_monthly_report(trade_dicts, month, year)
    
    # Telegram max message length is 4096. Report might suffice.
    await update.message.reply_text(report_md, parse_mode="Markdown")

async def handle_bias_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /bias command to check for trading errors."""
    db = context.bot_data["db"]
    repo = TradeRepository(db)
    
    trades = repo.get_all_closed_trades()
    trade_dicts = [t.model_dump() for t in trades]
    
    biases = detect_biases(trade_dicts)
    
    if not biases:
        await update.message.reply_text("✅ No significant behavioral biases detected.", parse_mode="Markdown")
    else:
        msg = "⚠️ **Behavioral Biases Detected:**\n\n"
        for b in biases:
            msg += f"- {b}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_scores_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /scores command to view adaptive strategy scores."""
    db = context.bot_data["db"]
    repo = TradeRepository(db)
    
    trades = repo.get_all_closed_trades()
    trade_dicts = [t.model_dump() for t in trades]
    
    scores = calculate_strategy_scores(trade_dicts)
    
    if not scores:
        await update.message.reply_text("ℹ️ Not enough data to calculate strategy scores.")
        return
        
    msg = "📊 **Adaptive Strategy Scores**\n\n"
    for strategy, score in scores.items():
        emoji = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"
        msg += f"{emoji} **{strategy}**: {score}\n"
        
    await update.message.reply_text(msg, parse_mode="Markdown")
