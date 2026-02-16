"""Tests for BotManager."""

from unittest.mock import MagicMock, patch
from bot.manager import BotManager

def test_bot_manager_init():
    mock_db = MagicMock()
    with patch("bot.manager.Application.builder") as MockBuilder:
        # Mocking the builder chain
        mock_builder_inst = MockBuilder.return_value
        mock_builder_inst.token.return_value = mock_builder_inst
        mock_app = MagicMock()
        mock_app.bot_data = {}
        mock_builder_inst.build.return_value = mock_app
        
        manager = BotManager(mock_db)
        
        assert manager.db == mock_db
        assert manager.app == mock_app
        assert mock_app.bot_data["db"] == mock_db
        # Verify handlers were added
        assert mock_app.add_handler.call_count == 3

@patch("bot.manager.Application.builder")
def test_bot_manager_run(MockBuilder):
    mock_db = MagicMock()
    mock_builder_inst = MockBuilder.return_value
    mock_builder_inst.token.return_value = mock_builder_inst
    mock_app = MagicMock()
    mock_app.bot_data = {}
    mock_builder_inst.build.return_value = mock_app
    
    manager = BotManager(mock_db)
    
    with patch.object(mock_app, "run_polling") as mock_run_polling:
        manager.run()
        mock_run_polling.assert_called_once_with(drop_pending_updates=True)
