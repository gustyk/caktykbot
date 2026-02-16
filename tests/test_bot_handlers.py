"""Unit tests for Telegram bot handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.watchlist import handle_add_stock, handle_list_watchlist, handle_remove_stock
from utils.exceptions import DuplicateStockError, StockRepoError, WatchlistFullError


@pytest.fixture
def mock_update():
    """Create a mock Telegram update."""
    update = MagicMock(spec=Update)
    update.message = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create a mock Telegram context."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    # Mock bot_data with a mock DB
    context.application.bot_data = {"db": MagicMock()}
    return context


@pytest.mark.asyncio
async def test_handle_add_stock_success(mock_update, mock_context):
    """Test successful /add command."""
    mock_context.args = ["BBCA.JK"]
    
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        await handle_add_stock(mock_update, mock_context)
        
        # Verify repo call
        MockRepo.return_value.add_stock.assert_called_once()
        # Verify success message
        mock_update.message.reply_text.assert_called_with("✅ BBCA.JK berhasil ditambahkan ke watchlist.")


@pytest.mark.asyncio
async def test_handle_add_stock_full(mock_update, mock_context):
    """Test /add command when watchlist is full."""
    mock_context.args = ["TLKM.JK"]
    
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        MockRepo.return_value.add_stock.side_effect = WatchlistFullError("Watchlist reached maximum limit")
        
        await handle_add_stock(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_with("❌ Gagal: Watchlist reached maximum limit")


@pytest.mark.asyncio
async def test_handle_add_stock_duplicate(mock_update, mock_context):
    """Test /add command for duplicate stock."""
    mock_context.args = ["ASII.JK"]
    
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        MockRepo.return_value.add_stock.side_effect = DuplicateStockError("Stock ASII.JK is already in watchlist")
        
        await handle_add_stock(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_with("❌ Gagal: Stock ASII.JK is already in watchlist")


@pytest.mark.asyncio
async def test_handle_remove_stock_success(mock_update, mock_context):
    """Test successful /remove command."""
    mock_context.args = ["UNVR.JK"]
    
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        await handle_remove_stock(mock_update, mock_context)
        
        MockRepo.return_value.deactivate_stock.assert_called_with("UNVR.JK")
        mock_update.message.reply_text.assert_called_with("🗑️ UNVR.JK telah dihapus dari watchlist aktif.")


@pytest.mark.asyncio
async def test_handle_list_watchlist_empty(mock_update, mock_context):
    """Test /watchlist empty state."""
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        MockRepo.return_value.get_all_stocks.return_value = []
        
        await handle_list_watchlist(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_with("Watchlist kosong. Gunakan /add untuk menambah stock.")


@pytest.mark.asyncio
async def test_handle_list_watchlist_with_data(mock_update, mock_context):
    """Test /watchlist with data."""
    mock_stock = MagicMock()
    mock_stock.symbol = "BBCA.JK"
    
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        MockRepo.return_value.get_all_stocks.return_value = [mock_stock]
        
        await handle_list_watchlist(mock_update, mock_context)
        
        # Check if output contains the symbol
        call_args = mock_update.message.reply_text.call_args
        assert "BBCA\\.JK" in call_args[0][0]
        assert call_args[1]["parse_mode"] == "MarkdownV2"


@pytest.mark.asyncio
async def test_handle_add_stock_full_error(mock_update, mock_context):
    """Test adding stock when watchlist is full."""
    from utils.exceptions import WatchlistFullError
    mock_context.args = ["BBCA.JK"]
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        mock_repo_inst = MockRepo.return_value
        mock_repo_inst.add_stock.side_effect = WatchlistFullError("Watchlist full")
        await handle_add_stock(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_with("❌ Gagal: Watchlist full")


@pytest.mark.asyncio
async def test_handle_add_stock_unexpected_error(mock_update, mock_context):
    """Test adding stock with an unexpected error."""
    mock_context.args = ["BBCA.JK"]
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        mock_repo_inst = MockRepo.return_value
        mock_repo_inst.add_stock.side_effect = Exception("Crash")
        await handle_add_stock(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_with(
            "❌ Terjadi kesalahan internal saat menambah stock."
        )


@pytest.mark.asyncio
async def test_handle_remove_stock_not_found(mock_update, mock_context):
    """Test removing a non-existent stock."""
    from utils.exceptions import StockNotFoundError
    mock_context.args = ["BBCA.JK"]
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        mock_repo_inst = MockRepo.return_value
        mock_repo_inst.deactivate_stock.side_effect = StockNotFoundError("Not found")
        await handle_remove_stock(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_with("❌ Gagal: Not found")


@pytest.mark.asyncio
async def test_handle_remove_stock_unexpected_error(mock_update, mock_context):
    """Test removing stock with an unexpected error."""
    mock_context.args = ["BBCA.JK"]
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        mock_repo_inst = MockRepo.return_value
        mock_repo_inst.deactivate_stock.side_effect = Exception("Crash")
        await handle_remove_stock(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_with(
            "❌ Terjadi kesalahan internal saat menghapus stock."
        )


@pytest.mark.asyncio
async def test_handle_list_watchlist_error(mock_update, mock_context):
    """Test listing watchlist with an error."""
    with patch("bot.handlers.watchlist.StockRepository") as MockRepo:
        mock_repo_inst = MockRepo.return_value
        mock_repo_inst.get_all_stocks.side_effect = Exception("Crash")
        await handle_list_watchlist(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_with("❌ Gagal mengambil data watchlist.")

@pytest.mark.asyncio
async def test_handle_add_stock_missing_args(mock_update, mock_context):
    mock_context.args = []
    await handle_add_stock(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Format salah. Gunakan: /add SYMBOL.JK\nContoh: /add BBCA.JK")

@pytest.mark.asyncio
async def test_handle_remove_stock_missing_args(mock_update, mock_context):
    mock_context.args = []
    await handle_remove_stock(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Format salah. Gunakan: /remove SYMBOL.JK")
