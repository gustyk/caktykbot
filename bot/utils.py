"""Bot utilities and decorators."""
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import settings

def is_admin(func):
    """Decorator to restrict command access to admin only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return
            
        user_id = update.effective_user.id
        # Allow if user_id matches TELEGRAM_CHAT_ID (assuming it's the admin ID)
        # or if we add a dedicated ADMIN_IDS list later.
        if str(user_id) != str(settings.TELEGRAM_CHAT_ID):
            await update.message.reply_text("❌ Anda tidak memiliki akses untuk perintah ini.")
            return
            
        return await func(update, context, *args, **kwargs)
    return wrapper
