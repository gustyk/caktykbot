"""Health check command handler."""
from telegram import Update
from telegram.ext import ContextTypes

from monitoring.health_check import check_all
from bot.utils import is_admin

@is_admin
async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /health command."""
    status_msg = await update.message.reply_text("🏥 Checking system health...")
    
    try:
        results = check_all()
        
        # Format message
        mongo_status = "✅" if results["mongodb"]["status"] == "ok" else "❌"
        api_status = "✅" if results["external_api"]["status"] == "ok" else "❌"
        
        pipeline_res = results["pipeline"]
        pipeline_icon = "✅"
        if pipeline_res["status"] == "warning":
            pipeline_icon = "⚠️"
        elif pipeline_res["status"] == "error":
            pipeline_icon = "❌"
            
        message = (
            f"<b>System Health Report</b>\n"
            f"Timestamp: {results['timestamp']}\n\n"
            
            f"<b>Database</b>\n"
            f"{mongo_status} MongoDB ({results['mongodb'].get('latency_ms', 0)}ms)\n\n"
            
            f"<b>External API</b>\n"
            f"{api_status} Yahoo Finance ({results['external_api'].get('latency_ms', 0)}ms)\n\n"
            
            f"<b>Data Pipeline</b>\n"
            f"{pipeline_icon} Last Run: {pipeline_res.get('last_run', 'N/A')}\n"
            f"Age: {pipeline_res.get('hours_since', 'N/A')}h\n"
            f"Success Rate: {pipeline_res.get('success_rate', 'N/A')}\n"
        )
        
        await status_msg.edit_text(message, parse_mode="HTML")
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Health check failed: {str(e)}")
