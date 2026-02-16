from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
import os

from db.connection import get_database
from db.repositories.trade_repo import TradeRepository
from analytics.monthly_report import generate_pdf_report, generate_markdown_report

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /report command.
    Usage:
    /report [month] [year] -> Generates PDF and Markdown summary
    """
    args = context.args
    now = datetime.now()
    
    # Defaults
    month = now.month
    year = now.year
    
    # Parse args
    if len(args) >= 1:
        if args[0].isdigit():
            month = int(args[0])
            # Handle previous month logic if user types just /report (usually means "last month")
            # But here defaults to current.
    
    if len(args) >= 2:
        if args[1].isdigit():
            year = int(args[1])
            
    # If no args provided, maybe assume "Last Month" if today is first week?
    # Or just current month so far. Let's strict to defaults or explicit.
    
    status_msg = await update.message.reply_text(f"📊 Generating report for {month}/{year}...")
    
    try:
        db = get_database()
        repo = TradeRepository(db)
        trades_objs = repo.get_all_closed_trades()
        trades = [t.model_dump() for t in trades_objs]
        
        # Markdown Summary
        md_report = generate_markdown_report(trades, month, year)
        
        # Check if empty (string starts with "No trades")
        if md_report.startswith("No trades"):
            await status_msg.edit_text(f"❌ {md_report}")
            return
            
        # Send Markdown
        await status_msg.edit_text(md_report, parse_mode="Markdown")
        
        # Generate PDF
        pdf_path = generate_pdf_report(trades, month, year)
        
        if pdf_path and os.path.exists(pdf_path):
            await update.message.reply_document(
                document=open(pdf_path, 'rb'),
                filename=os.path.basename(pdf_path),
                caption=f"📄 Detailed Report {month}/{year}"
            )
            # Cleanup
            # os.remove(pdf_path) # Maybe keep for a bit or rely on temp cleaner? 
            # Safe to remove after verify?
            # Telegram might need file open during send? 
            # create task to remove later? or just leave in temp.
            pass
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Error generating report: {e}")
