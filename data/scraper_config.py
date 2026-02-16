import random
import time

class ScraperConfig:
    """
    Configuration for IDX Scraper
    """
    IDX_BASE_URL = "https://www.idx.co.id/primary/TradingSummary" # Placeholder URL
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_BACKOFF_FACTOR = 2  # 1.5s -> 3s -> 6s
    REQUEST_DELAY = 1.5       # Delay between requests to avoid rate limiting
    
    # Headers
    BASE_HEADERS = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
    }

    # User Agent List
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    ]
    
    @staticmethod
    def get_headers():
        user_agent = random.choice(ScraperConfig.USER_AGENTS)
            
        headers = ScraperConfig.BASE_HEADERS.copy()
        headers["User-Agent"] = user_agent
        return headers

    @staticmethod
    def get_delay():
        # Add random jitter to delay
        return ScraperConfig.REQUEST_DELAY + random.uniform(0.1, 0.5)
