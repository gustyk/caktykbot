"""Handler untuk /start, /menu, dan callback tombol inline keyboard.

Best-practice Telegram UX:
  - /start  → sambutan + tombol menu utama (InlineKeyboardMarkup)
  - /menu   → sama dengan /start (alias)
  - Callback buttons → sub-menu atau shortcut command info
  - Semua kategori dikelompokkan: 📊 Analisis, 📒 Journal, ⚙️ Portfolio, 🛡 Risk
"""
from __future__ import annotations

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
)
from loguru import logger


# ── Teks & keyboard ────────────────────────────────────────────────────────────

_WELCOME = (
    "👋 *Halo\\! Selamat datang di CakTykBot*\n\n"
    "🤖 Asisten trading IDX otomatis Anda \\— sinyal, jurnal, risk management, "
    "dan analisis teknikal dalam satu bot\\.\n\n"
    "Pilih kategori di bawah untuk melihat perintah yang tersedia:"
)

# Keyboard menu utama
_MAIN_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📊 Analisis & Sinyal", callback_data="menu_analysis"),
        InlineKeyboardButton("📋 Watchlist",          callback_data="menu_watchlist"),
    ],
    [
        InlineKeyboardButton("📒 Jurnal Trading",     callback_data="menu_journal"),
        InlineKeyboardButton("🛡 Risk Management",    callback_data="menu_risk"),
    ],
    [
        InlineKeyboardButton("⚙️ Portfolio & Setup",  callback_data="menu_portfolio"),
        InlineKeyboardButton("🔬 Riset & Backtest",   callback_data="menu_research"),
    ],
    [
        InlineKeyboardButton("❓ Semua Perintah",     callback_data="menu_all"),
    ],
])

# ── Sub-menu teks ──────────────────────────────────────────────────────────────

_MENUS: dict[str, tuple[str, InlineKeyboardMarkup]] = {

    "menu_analysis": (
        "📊 *Analisis \\& Sinyal*\n\n"
        "`/signal` — Sinyal BUY hari ini dari semua strategi \\(VCP \\+ EMA Pullback\\)\n"
        "`/analyze BBCA\\.JK` — Analisis teknikal mendalam 1 saham\n"
        "`/bandar BBCA\\.JK` — Deteksi pola Bandarmologi \\(akumulasi broker\\)\n"
        "`/bias` — Market bias IHSG saat ini \\(bullish / bearish / netral\\)\n"
        "`/scores` — Skor adaptif setiap strategi berdasarkan historis\n\n"
        "💡 _Gunakan sinyal sebagai referensi, bukan saran investasi\\._",
        InlineKeyboardMarkup([[
            InlineKeyboardButton("◀ Kembali", callback_data="menu_back"),
        ]]),
    ),

    "menu_watchlist": (
        "📋 *Watchlist*\n\n"
        "`/watchlist` — Tampilkan semua saham aktif di watchlist\n"
        "`/add BBCA\\.JK` — Tambah saham ke watchlist\n"
        "`/remove BBCA\\.JK` — Hapus saham dari watchlist\n"
        "`/follow BBCA\\.JK` — Follow sinyal otomatis untuk saham tertentu\n\n"
        "📎 _Format ticker: KODE\\.JK \\(contoh: BBCA\\.JK, BUMI\\.JK\\)_",
        InlineKeyboardMarkup([[
            InlineKeyboardButton("◀ Kembali", callback_data="menu_back"),
        ]]),
    ),

    "menu_journal": (
        "📒 *Jurnal Trading*\n\n"
        "`/journal` — Lihat semua posisi terbuka \\& riwayat trade\n"
        "`/stats` — Statistik P\\&L: win rate, avg profit, streak\n"
        "`/trade ID` — Detail 1 trade berdasarkan ID\n"
        "`/export` — Export semua trade ke file CSV\n\n"
        "✏️ *Entry \\& Exit Trade:*\n"
        "Gunakan `/addtrade` untuk membuka posisi baru \\(ikuti panduan interaktif\\)\n"
        "Gunakan `/closetrade` untuk menutup posisi \\(ikuti panduan interaktif\\)",
        InlineKeyboardMarkup([[
            InlineKeyboardButton("◀ Kembali", callback_data="menu_back"),
        ]]),
    ),

    "menu_risk": (
        "🛡 *Risk Management*\n\n"
        "`/heat` — Portfolio heat saat ini \\(% modal yang sedang berisiko\\)\n"
        "`/size BBCA\\.JK 9000 8500` — Hitung lot size optimal\n"
        "  ↳ Format: `/size TICKER ENTRY SL`\n\n"
        "🔢 *Rumus Sizing:*\n"
        "Lot \\= \\(Modal × Risk%\\) ÷ \\(Entry \\- SL\\) ÷ 100\n\n"
        "⚡ _Circuit breaker otomatis aktif jika heat melebihi batas\\._",
        InlineKeyboardMarkup([[
            InlineKeyboardButton("◀ Kembali", callback_data="menu_back"),
        ]]),
    ),

    "menu_portfolio": (
        "⚙️ *Portfolio \\& Setup*\n\n"
        "`/capital 100000000` — Set total modal \\(dalam Rupiah\\)\n"
        "`/risk 2` — Set max risk per trade \\(dalam %\\)\n"
        "`/confirm` — Konfirmasi follow sinyal yang pending\n"
        "`/health` — Status sistem bot \\(DB, scheduler, versi\\)\n\n"
        "💰 _Contoh: `/capital 50000000` = Rp 50 juta_",
        InlineKeyboardMarkup([[
            InlineKeyboardButton("◀ Kembali", callback_data="menu_back"),
        ]]),
    ),

    "menu_research": (
        "🔬 *Riset \\& Backtest*\n\n"
        "`/backtest BBCA\\.JK` — Uji strategi pada data historis saham\n"
        "`/report` — Laporan performa strategi periode ini\n"
        "`/scores` — Ranking strategi berdasarkan win rate adaptif\n\n"
        "⏱ _Backtest menggunakan data 2 tahun terakhir\\._",
        InlineKeyboardMarkup([[
            InlineKeyboardButton("◀ Kembali", callback_data="menu_back"),
        ]]),
    ),

    "menu_all": (
        "📖 *Semua Perintah CakTykBot*\n\n"
        "📊 *ANALISIS*\n"
        "`/signal` `/analyze` `/bandar` `/bias` `/scores`\n\n"
        "📋 *WATCHLIST*\n"
        "`/watchlist` `/add` `/remove` `/follow`\n\n"
        "📒 *JURNAL*\n"
        "`/journal` `/stats` `/trade` `/export`\n"
        "`/addtrade` `/closetrade` `/confirm`\n\n"
        "🛡 *RISK*\n"
        "`/heat` `/size`\n\n"
        "⚙️ *PORTFOLIO*\n"
        "`/capital` `/risk` `/health`\n\n"
        "🔬 *RISET*\n"
        "`/backtest` `/report`\n\n"
        "ℹ️ *BANTUAN*\n"
        "`/menu` `/start`",
        InlineKeyboardMarkup([[
            InlineKeyboardButton("◀ Kembali", callback_data="menu_back"),
        ]]),
    ),
}


# ── Handler functions ─────────────────────────────────────────────────────────

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — kirim sambutan + main menu keyboard."""
    await update.message.reply_text(
        _WELCOME,
        parse_mode="MarkdownV2",
        reply_markup=_MAIN_KEYBOARD,
    )


async def handle_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu — alias untuk /start, selalu tampilkan menu utama."""
    await update.message.reply_text(
        _WELCOME,
        parse_mode="MarkdownV2",
        reply_markup=_MAIN_KEYBOARD,
    )


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle semua inline keyboard callback dari menu."""
    query = update.callback_query
    await query.answer()  # hapus loading indicator

    data = query.data

    if data == "menu_back":
        # Kembali ke menu utama
        await query.edit_message_text(
            _WELCOME,
            parse_mode="MarkdownV2",
            reply_markup=_MAIN_KEYBOARD,
        )
        return

    if data in _MENUS:
        text, keyboard = _MENUS[data]
        await query.edit_message_text(
            text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
        return

    logger.warning(f"Unknown menu callback: {data}")


# ── CallbackQueryHandler yang bisa langsung di-register ───────────────────────

menu_callback_handler = CallbackQueryHandler(
    handle_menu_callback,
    pattern=r"^menu_",
)
