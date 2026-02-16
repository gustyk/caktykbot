import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from db.repositories.broker_repo import BrokerRepository
from db.repositories.foreign_flow_repo import ForeignFlowRepository
from db.schemas import BrokerSummaryBase, ForeignFlowBase
from data.idx_scraper import IDXScraper, ScraperConfig

class TestBrokerRepository:
    def test_add_summary(self, mongo_test_db):
        repo = BrokerRepository(mongo_test_db)
        summary = BrokerSummaryBase(
            symbol="BBCA.JK",
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            broker_code="YP",
            broker_name="Mirae",
            buy_value=1000,
            sell_value=500,
            net_value=500,
            buy_lot=10,
            sell_lot=5
        )
        result = repo.add_summary(summary)
        assert result.symbol == "BBCA.JK"
        assert result.net_value == 500
        
    def test_get_by_date(self, mongo_test_db):
        repo = BrokerRepository(mongo_test_db)
        summary = BrokerSummaryBase(
            symbol="BBCA.JK",
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            broker_code="YP",
            broker_name="Mirae",
            buy_value=1000, sell_value=500, net_value=500, buy_lot=10, sell_lot=5
        )
        repo.add_summary(summary)
        
        results = repo.get_by_date("BBCA.JK", datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert len(results) == 1
        assert results[0].broker_code == "YP"

    def test_get_latest(self, mongo_test_db):
        repo = BrokerRepository(mongo_test_db)
        # Add old data
        repo.add_summary(BrokerSummaryBase(
            symbol="BBCA.JK",
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            broker_code="YP", broker_name="Mirae", buy_value=100, sell_value=100, net_value=0, buy_lot=1, sell_lot=1
        ))
        # Add new data
        repo.add_summary(BrokerSummaryBase(
            symbol="BBCA.JK",
            date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            broker_code="YP", broker_name="Mirae", buy_value=200, sell_value=100, net_value=100, buy_lot=2, sell_lot=1
        ))
        
        latest = repo.get_latest("BBCA.JK")
        assert len(latest) == 1
        assert latest[0].date == datetime(2024, 1, 2, tzinfo=timezone.utc)
        assert latest[0].buy_value == 200

class TestForeignFlowRepository:
    def test_add_flow(self, mongo_test_db):
        repo = ForeignFlowRepository(mongo_test_db)
        flow = ForeignFlowBase(
            symbol="BBCA.JK",
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            foreign_buy=1000, foreign_sell=500, foreign_net=500, foreign_ratio=0.5
        )
        result = repo.add_flow(flow)
        assert result.symbol == "BBCA.JK"
        assert result.foreign_net == 500

    def test_get_history(self, mongo_test_db):
        repo = ForeignFlowRepository(mongo_test_db)
        for i in range(1, 4):
            repo.add_flow(ForeignFlowBase(
                symbol="BBCA.JK",
                date=datetime(2024, 1, i, tzinfo=timezone.utc),
                foreign_buy=1000, foreign_sell=500, foreign_net=500, foreign_ratio=0.5
            ))
            
        history = repo.get_history("BBCA.JK", limit=2)
        assert len(history) == 2
        assert history[0].date == datetime(2024, 1, 3, tzinfo=timezone.utc)

class TestIDXScraper:
    @patch('data.idx_scraper.requests.Session.get')
    def test_scrape_broker_summary_success(self, mock_get):
        scraper = IDXScraper()
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "brokers": [
                {"code": "YP", "name": "Mirae", "buy_val": 1000, "sell_val": 500, "buy_vol": 10, "sell_vol": 5}
            ]
        }
        mock_get.return_value = mock_response
        
        results = scraper.scrape_broker_summary("BBCA.JK", "2024-01-01")
        assert len(results) == 1
        assert results[0]["broker_code"] == "YP"
        assert results[0]["net_value"] == 500

    @patch('data.idx_scraper.requests.Session.get')
    def test_scrape_foreign_flow_success(self, mock_get):
        scraper = IDXScraper()
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "foreign": {
                "buy_val": 1000,
                "sell_val": 500,
                "net_val": 500,
                "ratio": 0.5
            }
        }
        mock_get.return_value = mock_response
        
        result = scraper.scrape_foreign_flow("BBCA.JK", "2024-01-01")
        assert result is not None
        assert result["foreign_net"] == 500

    @patch('data.idx_scraper.requests.Session.get')
    def test_scrape_rate_limit_retry(self, mock_get):
        scraper = IDXScraper()
        scraper.config.MAX_RETRIES = 2
        scraper.config.REQUEST_DELAY = 0.1 # fast test
        
        # First call 429, second 200
        mock_response_limit = Mock()
        mock_response_limit.status_code = 429
        
        mock_response_ok = Mock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {"brokers": []}
        
        mock_get.side_effect = [mock_response_limit, mock_response_ok]
        
        scraper.scrape_broker_summary("BBCA.JK", "2024-01-01")
        assert mock_get.call_count == 2
