"""Handlers for portfolio configuration commands."""
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from db.repositories.portfolio_repo import PortfolioRepository
from db.schemas import PortfolioConfig


async def handle_capital_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /capital command to set or view total capital."""
    db = context.bot_data["db"]
    repo = PortfolioRepository(db)
    user = "nesa" # Single user default

    if not context.args:
        # View current capital
        config = repo.get_config(user)
        if config:
            await update.message.reply_text(
                f"💰 *Current Capital*: Rp {config.total_capital:,.0f}\n"
                f"⚠️ *Risk per Trade*: {config.risk_per_trade*100:.1f}%",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Portfolio not configured. Use `/capital <AMOUNT>` to set.")
        return

    try:
        amount_str = context.args[0].replace(",", "").replace(".", "")
        amount = float(amount_str)
        
        if amount <= 0:
            await update.message.reply_text("❌ Capital must be greater than 0.")
            return

        config = repo.get_config(user)
        if config:
            repo.update_capital(user, amount)
        else:
            # Create working default if not exists
            new_config = PortfolioConfig(
                user=user,
                total_capital=amount,
                risk_per_trade=0.01  # Default 1%
            )
            repo.upsert_config(new_config)

        await update.message.reply_text(f"✅ Capital updated: Rp {amount:,.0f}")

    except ValueError:
        await update.message.reply_text("❌ Invalid amount format. Use numbers only (e.g., 100000000).")
    except Exception as e:
        logger.error(f"Error in /capital: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_risk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /risk command to set or view risk per trade."""
    db = context.bot_data["db"]
    repo = PortfolioRepository(db)
    user = "nesa"

    if not context.args:
        config = repo.get_config(user)
        if config:
            await update.message.reply_text(
                f"⚠️ *Risk per Trade*: {config.risk_per_trade*100:.1f}%\n"
                f"Use `/risk <PERCENT>` to change (e.g., `/risk 1` for 1%)",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Portfolio not configured. Use `/capital` first.")
        return

    try:
        risk_str = context.args[0].replace("%", "")
        risk_pct = float(risk_str)
        
        # Validation
        if risk_pct < 0.1 or risk_pct > 5.0:
            await update.message.reply_text("❌ Risk must be between 0.1% and 5%. Recommended: 0.5% - 2%.")
            return
            
        risk_decimal = risk_pct / 100.0
        
        config = repo.get_config(user)
        if config:
            repo.update_risk(user, risk_decimal)
            await update.message.reply_text(f"✅ Risk per trade updated: {risk_pct}%")
        else:
            await update.message.reply_text("❌ Set `/capital` first before setting risk.")

    except ValueError:
        await update.message.reply_text("❌ Invalid format. Use numbers (e.g., 1 or 0.5).")
    except Exception as e:
        logger.error(f"Error in /risk: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
