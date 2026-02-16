import logging
import time
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Any
from .scraper_config import ScraperConfig

# Set up logger
logger = logging.getLogger(__name__)

class IDXScraper:
    def __init__(self):
        self.config = ScraperConfig()
        self.session = requests.Session()

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        """
        Helper to make HTTP requests with retry logic and rotation.
        """
        retries = 0
        backoff = self.config.REQUEST_DELAY
        
        while retries < self.config.MAX_RETRIES:
            try:
                headers = self.config.get_headers()
                # Respect rate limiting
                time.sleep(self.config.get_delay())
                
                response = self.session.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    logger.warning(f"Rate limited (429). Retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= self.config.RETRY_BACKOFF_FACTOR
                    retries += 1
                elif response.status_code == 403:
                    logger.critical("Blocked (403). Stop scraping.")
                    return None
                else:
                    logger.error(f"HTTP {response.status_code} for {url}")
                    retries += 1
                    
            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                retries += 1
                time.sleep(backoff)
                
        return None

    def scrape_broker_summary(self, symbol: str, date: str) -> List[Dict[str, Any]]:
        """
        Scrape top broker summary for a symbol on a specific date.
        
        Note: Actual logic depends on the specific endpoint structure. 
        This is a schematic implementation aimed at the data structure defined in the plan.
        """
        # Placeholder endpoint logic - replaceme with actual endpoint
        # e.g., https://api.idx.co.id/.../broker_summary?symbol=ASII&date=2023-10-27
        url = f"{self.config.IDX_BASE_URL}/broker_summary" 
        params = {"symbol": symbol, "date": date}
        
        response = self._make_request(url, params)
        if not response:
            return []
            
        try:
            data = response.json()
            # Process data to match schema
            # expected data list of dicts: broker_code, broker_name, buy_value, sell_value, etc.
            results = []
            for item in data.get('brokers', []):
                summary = {
                    "symbol": symbol,
                    "date": date,
                    "broker_code": item.get("code"),
                    "broker_name": item.get("name"),
                    "buy_value": float(item.get("buy_val", 0)),
                    "sell_value": float(item.get("sell_val", 0)),
                    "net_value": float(item.get("buy_val", 0)) - float(item.get("sell_val", 0)),
                    "buy_lot": int(item.get("buy_vol", 0)),
                    "sell_lot": int(item.get("sell_vol", 0)),
                    "created_at": datetime.now()
                }
                results.append(summary)
            
            logger.info(f"Scraped broker summary for {symbol}: {len(results)} records.")
            return results
            
        except ValueError as e:
            logger.error(f"Failed to parse JSON for {symbol}: {e}")
            return []

    def scrape_foreign_flow(self, symbol: str, date: str) -> Optional[Dict[str, Any]]:
        """
        Scrape foreign flow data.
        """
        url = f"{self.config.IDX_BASE_URL}/foreign_flow"
        params = {"symbol": symbol, "date": date}
        
        response = self._make_request(url, params)
        if not response:
            return None
            
        try:
            data = response.json()
            item = data.get('foreign', {})
            
            # Defensive check
            if not item:
                return None
                
            result = {
                 "symbol": symbol,
                 "date": date,
                 "foreign_buy": float(item.get("buy_val", 0)),
                 "foreign_sell": float(item.get("sell_val", 0)),
                 "foreign_net": float(item.get("net_val", 0)),
                 "foreign_ratio": float(item.get("ratio", 0)), # e.g., 0.45 for 45%
                 "created_at": datetime.now()
            }
            logger.info(f"Scraped foreign flow for {symbol}: Net {result['foreign_net']}")
            return result
            
        except ValueError:
            logger.error(f"Failed to parse JSON foreign flow for {symbol}")
            return None

    def scrape_all_watchlist(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Orchestrate batch scraping.
        """
        results = {
            "success_count": 0,
            "failed_symbols": [],
            "broker_data": [],
            "foreign_data": []
        }
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        for symbol in symbols:
            # Broker Summary
            brokers = self.scrape_broker_summary(symbol, today_str)
            if brokers:
                results["broker_data"].extend(brokers)
            
            # Foreign Flow
            foreign = self.scrape_foreign_flow(symbol, today_str)
            if foreign:
                results["foreign_data"].append(foreign)
            
            if brokers or foreign:
                results["success_count"] += 1
            else:
                results["failed_symbols"].append(symbol)
                
        return results
