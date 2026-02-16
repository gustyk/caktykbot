"""Handler for /analyze command."""
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from db.repositories.price_repo import PriceRepository
from db.repositories.stock_repo import StockRepository
from strategies.vcp import VCPStrategy
from strategies.ema_pullback import EMAPullbackStrategy
from engine.signal_generator import SignalGenerator
from data.pipeline import DataPipeline  # Optional: logic to fetch latest data if not present?
# For now, we rely on existing data in DB.


async def handle_analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyze a single stock on demand."""
    if not context.args:
        await update.message.reply_text("Usage: `/analyze <TICKER>`\nContoh: `/analyze BBCA`", parse_mode="Markdown")
        return

    symbol = context.args[0].upper()
    if not symbol.endswith(".JK"):
        symbol += ".JK"
    
    msg = await update.message.reply_text(f"🔍 Analyzing {symbol}...")
    
    try:
        db = context.bot_data["db"]
        price_repo = PriceRepository(db)
        stock_repo = StockRepository(db)
        
        # Check if stock exists
        stock = stock_repo.get_stock(symbol)
        if not stock:
            await msg.edit_text(f"❌ Stock '{symbol}' not found in watchlist.")
            return

        # Get Data (last 250 days)
        prices = price_repo.get_historical_prices(symbol, limit=250)
        if len(prices) < 200:
            await msg.edit_text(f"❌ Insufficient data for {symbol} ({len(prices)}/200 days).")
            return
            
        # Convert to DataFrame
        # DailyPriceInDB model -> dict -> DataFrame
        df = pd.DataFrame([p.model_dump() for p in prices])
        # Standardize column names to TitleCase for strategies
        df = df.rename(columns={
            "open": "Open", 
            "high": "High", 
            "low": "Low", 
            "close": "Close", 
            "volume": "Volume"
        })
        # Sort ascending by date for analysis
        df = df.sort_values("date", ascending=True).reset_index(drop=True)
        
        # Get IHSG Data for RS calc (simplified: get IHSG or skip RS if logic complex)
        # Ideally we fetch IHSG from DB. Assuming 'COMPOSITE.JK' or 'IHSG' is in DB?
        # Sprint 2 Plan says "IHSG data ... gap-fill ...".
        # For now, let's try to get ^JKSE or similar if available, or pass None.
        ihsg_prices = price_repo.get_historical_prices("^JKSE", limit=250) # Assuming symbol for IHSG
        ihsg_df = None
        if ihsg_prices:
             ihsg_df = pd.DataFrame([p.model_dump() for p in ihsg_prices]).sort_values("date").reset_index(drop=True)
             ihsg_df = ihsg_df.rename(columns={
                "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
             })
        
        # Run Strategies
        vcp = VCPStrategy()
        ema = EMAPullbackStrategy()
        
        vcp_sig = vcp.analyze(df, symbol=symbol)
        ema_sig = ema.analyze(df, symbol=symbol, ihsg_data=ihsg_df)
        
        # Run Engine
        engine = SignalGenerator()
        final_sig = engine.generate(symbol, [vcp_sig, ema_sig])
        
        # Format Output
        last_price = df.iloc[-1]["Close"]
        change_pct = 0.0
        if len(df) > 1:
            prev_close = df.iloc[-2]["Close"]
            change_pct = ((last_price - prev_close) / prev_close) * 100
        
        icon = "🟢" if final_sig.verdict == "BUY" else "⚪"
        
        response = [
            f"🔍 *Analysis: {symbol}*",
            f"Price: {last_price:,.0f} ({change_pct:+.2f}%)",
            "",
            f"🎯 *Verdict: {final_sig.verdict}* {icon}",
            f"Confidence: {final_sig.confidence} | Score: {final_sig.tech_score:.0f}",
            f"Reasoning: {final_sig.reasoning}",
            "",
            "*Strategy Details:*",
        ]
        
        if vcp_sig:
            response.append(f"• VCP: ✅ BUY (Score: {vcp_sig.score})")
        else:
            response.append("• VCP: ❌ No Signal")
            
        if ema_sig:
            response.append(f"• EMA: ✅ BUY (Score: {ema_sig.score})")
        else:
            response.append("• EMA: ❌ No Signal")
            
        if final_sig.verdict == "BUY":
            response.append("")
            response.append(f"*Plan:*")
            response.append(f"Entry: {final_sig.entry_price:,.0f}")
            response.append(f"SL: {final_sig.sl_price:,.0f}")
            response.append(f"TP: {final_sig.tp_price:,.0f}")
            
        await msg.edit_text("\n".join(response), parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in /analyze: {e}")
        await msg.edit_text(f"❌ Analysis failed: {str(e)}")
