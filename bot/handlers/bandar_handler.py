from telegram import Update
from telegram.ext import ContextTypes
import pandas as pd
from db.repositories.broker_repo import BrokerRepository
from db.repositories.foreign_flow_repo import ForeignFlowRepository
from strategies.bandarmologi import BandarmologiStrategy

async def handle_bandar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /bandar <SYMBOL> command."""
    if not context.args:
        await update.message.reply_text("❌ Usage: `/bandar <SYMBOL>` (e.g. `/bandar BBCA`)")
        return
        
    symbol = context.args[0].upper()
    if not symbol.endswith(".JK"):
        symbol += ".JK"
        
    db = context.bot_data["db"]
    broker_repo = BrokerRepository(db)
    flow_repo = ForeignFlowRepository(db)
    
    # Fetch Data
    # Get last 10 days for analysis
    # Note: Repos normally return list of objects.
    # Convert to DataFrame for Strategy
    
    broker_summary = broker_repo.get_latest(symbol, limit=10)
    flow_summary = flow_repo.get_history(symbol, limit=10)
    
    if not broker_summary and not flow_summary:
        await update.message.reply_text(f"❌ No bandarmologi data found for {symbol}.")
        return
        
    # Convert to DataFrame
    broker_dicts = [b.model_dump() for b in broker_summary]
    flow_dicts = [f.model_dump() for f in flow_summary]
    
    broker_df = pd.DataFrame(broker_dicts) if broker_dicts else pd.DataFrame()
    flow_df = pd.DataFrame(flow_dicts) if flow_dicts else pd.DataFrame()
    
    # Initialize Strategy for detection methods
    strategy = BandarmologiStrategy()
    
    msg = f"🕵️ **Bandarmologi Analysis: {symbol}**\n\n"
    
    # Accumulation Analysis
    if not broker_df.empty:
        accum = strategy.detect_accumulation(broker_df)
        status = "✅ Accumulation" if accum["is_accumulating"] else "neutral"
        msg += f"**Broker Summary**: {status}\n"
        if accum["is_accumulating"]:
            msg += f"- Top Buyers: {', '.join(accum['top_brokers'])}\n"
            msg += f"- Est. Value: Rp {accum['top_buy_val']/1e9:.1f} M\n"
    else:
        msg += "**Broker Summary**: No Data\n"
        
    msg += "\n"
    
    # Foreign Flow Analysis
    if not flow_df.empty:
        foreign = strategy.detect_foreign_flow(flow_df)
        status = "✅ Net Buy" if foreign["is_foreign_buying"] else "neutral" # Or Net Sell check
        net_val = foreign['net_7d']
        
        msg += f"**Foreign Flow**: {status}\n"
        direction = "Inflow" if net_val > 0 else "Outflow"
        msg += f"- 1W Net: {direction} Rp {abs(net_val)/1e9:.1f} M\n"
        if foreign["is_foreign_buying"]:
            msg += f"- Streak: {foreign['consecutive_days']} days\n"
            
    else:
        msg += "**Foreign Flow**: No Data\n"
        
    await update.message.reply_text(msg, parse_mode="Markdown")
