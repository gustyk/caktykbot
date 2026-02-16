# CakTykBot

Automated stock trading bot for Indonesian market (IDX) with technical analysis and risk management.

## 🎯 Sprint 1: Foundation & Data Backbone

**Status**: ✅ In Development  
**Version**: 0.1.0  
**Python**: 3.11+

## 📋 Features (Sprint 1)

- ✅ Watchlist management (up to 20 stocks)
- ✅ Daily OHLCV data fetching from yfinance
- ✅ Technical indicators (EMA 8/21/50/150/200, ATR 14, Volume MA 20)
- ✅ MongoDB Atlas integration
- ✅ Telegram bot interface
- ✅ Automated scheduler (18:45 WIB daily)
- ✅ Comprehensive error handling and validation

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- MongoDB Atlas account (M0 free tier)
- Telegram Bot Token (from @BotFather)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd caktykbot
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

5. **Setup MongoDB indexes** (first time only)
   ```bash
   python -c "from db.connection import setup_indexes; setup_indexes()"
   ```

### Configuration

Edit `.env` file with your credentials:

```env
# MongoDB Configuration
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=caktykbot

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Application Configuration
MAX_WATCHLIST=20
FETCH_RETRY_COUNT=3
FETCH_RETRY_DELAY=2.0
LOG_LEVEL=INFO
TIMEZONE=Asia/Jakarta
ENVIRONMENT=development
```

## 📖 Usage

### Manual Commands

```bash
# Fetch data for all stocks in watchlist (manual trigger)
python main.py fetch

# Backfill historical data (3 years)
python main.py backfill --days 1095

# Start Telegram bot (long-polling mode)
python main.py bot

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=. --cov-report=html
```

### Telegram Bot Commands

- `/watchlist` - Show current watchlist
- `/add CODE.JK` - Add stock to watchlist (e.g., `/add BBCA.JK`)
- `/remove CODE.JK` - Remove stock from watchlist
- `/status` - Show bot status and last pipeline run

### Automated Scheduler

The pipeline runs automatically every day at **18:45 WIB** (after market closes at 15:50 WIB).

To start the scheduler:
```bash
python -m scheduler.jobs
```

## 🏗️ Project Structure

```
caktykbot/
├── config/              # Configuration and settings
│   ├── settings.py      # Pydantic settings with validation
│   └── logging.py       # Logging configuration
├── data/                # Data fetching and processing
│   ├── fetcher.py       # yfinance data fetcher
│   ├── indicators.py    # Technical indicator calculations
│   ├── pipeline.py      # Pipeline orchestrator
│   └── validators.py    # DataFrame validation
├── db/                  # Database layer
│   ├── connection.py    # MongoDB connection (thread-safe)
│   ├── schemas.py       # Pydantic models
│   └── repositories/    # CRUD operations
│       ├── stock_repo.py
│       └── price_repo.py
├── bot/                 # Telegram bot
│   ├── telegram_bot.py
│   └── handlers/
│       └── watchlist_handler.py
├── scheduler/           # Cron jobs
│   └── jobs.py
├── utils/               # Utilities
│   ├── exceptions.py    # Custom exceptions
│   ├── rate_limiter.py  # Adaptive rate limiting
│   ├── circuit_breaker.py
│   └── timezone.py
└── tests/               # Test suite
    ├── test_fetcher.py
    ├── test_indicators.py
    ├── test_validators.py
    ├── test_pipeline.py
    └── test_integration.py
```

## 🧪 Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Types
```bash
# Unit tests only
pytest tests/ -v -m "not integration and not chaos"

# Integration tests
pytest tests/ -v -m integration

# Chaos engineering tests
pytest tests/ -v -m chaos

# Performance benchmarks
pytest tests/ -v -m benchmark --benchmark-only
```

### Coverage Report
```bash
pytest tests/ --cov=. --cov-report=html
# Open htmlcov/index.html in browser
```

## 🚢 Deployment (Railway)

### Prerequisites
- Railway account
- Railway CLI installed

### Deployment Steps

1. **Install Railway CLI**
   ```bash
   npm install -g @railway/cli
   ```

2. **Login to Railway**
   ```bash
   railway login
   ```

3. **Initialize project**
   ```bash
   railway init
   railway link
   ```

4. **Set environment variables**
   ```bash
   railway variables set MONGO_URI="mongodb+srv://..."
   railway variables set TELEGRAM_BOT_TOKEN="123456789:ABC..."
   railway variables set TELEGRAM_CHAT_ID="123456"
   railway variables set TZ="Asia/Jakarta"
   railway variables set ENVIRONMENT="production"
   railway variables set LOG_LEVEL="INFO"
   ```

5. **Deploy**
   ```bash
   railway up
   ```

6. **View logs**
   ```bash
   railway logs --tail
   ```

### Post-Deployment Verification

- ✅ Service status: `railway status`
- ✅ Logs show "Scheduler started"
- ✅ MongoDB connection successful
- ✅ Telegram bot responds to `/watchlist`
- ✅ Pipeline runs at 18:45 WIB

## 📊 Database Schema

### Collection: `stocks` (Watchlist)
- `symbol` (string, unique): Ticker code (e.g., "BBCA.JK")
- `name` (string): Company name
- `sector` (string): Sector classification
- `market_cap` (enum): large/mid/small
- `is_active` (boolean): Active in watchlist
- `added_at` (datetime): Date added
- `updated_at` (datetime): Last updated

### Collection: `daily_prices` (Time Series)
- `symbol` (string): Ticker code
- `date` (datetime): Trading date
- `open`, `high`, `low`, `close` (float): OHLC prices
- `volume` (int): Trading volume
- `adjusted_close` (float): Adjusted close price
- `ema_8`, `ema_21`, `ema_50`, `ema_150`, `ema_200` (float): EMA indicators
- `atr_14` (float): Average True Range
- `vol_ma_20` (float): Volume moving average
- `fetched_at` (datetime): Fetch timestamp

### Collection: `pipeline_runs` (Observability)
- `date` (datetime): Run date
- `duration` (float): Duration in seconds
- `success_count` (int): Successful stocks
- `fail_count` (int): Failed stocks
- `errors` (list): Error messages

## 🔧 Development

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .

# Type checking
mypy .
```

### Pre-commit Checks

```bash
# Run all checks
black . && ruff check . && pytest tests/ --cov=. --cov-fail-under=90
```

## 📝 Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGO_URI` | ✅ Yes | - | MongoDB connection string |
| `MONGO_DB_NAME` | No | caktykbot | Database name |
| `TELEGRAM_BOT_TOKEN` | ✅ Yes | - | Telegram bot token |
| `TELEGRAM_CHAT_ID` | ✅ Yes | - | Telegram chat ID |
| `MAX_WATCHLIST` | No | 20 | Maximum stocks in watchlist |
| `FETCH_RETRY_COUNT` | No | 3 | Number of retries for failed fetches |
| `FETCH_RETRY_DELAY` | No | 2.0 | Delay between retries (seconds) |
| `LOG_LEVEL` | No | INFO | Logging level |
| `TIMEZONE` | No | Asia/Jakarta | Timezone for scheduler |
| `ENVIRONMENT` | No | development | Environment (development/production) |

## ⚠️ Important Notes

### Deployment Platform
- ❌ **Vercel is NOT supported** (serverless limitation)
- ✅ **Railway is the recommended platform**

### Timezone Configuration
- **CRITICAL**: Set `TZ=Asia/Jakarta` in Railway environment variables
- Without this, scheduler will run 7 hours early (UTC instead of WIB)

### Python Version
- Local development: Python 3.14.0 (your current version)
- Production (Railway): Python 3.11 (locked in `runtime.txt`)

### Rate Limiting
- yfinance has undocumented rate limits (~10 req/min soft limit)
- Adaptive rate limiter with 70% safety buffer implemented
- Max 5 concurrent workers to prevent IP bans

## 🐛 Troubleshooting

### MongoDB Connection Fails
```bash
# Check if MONGO_URI is correct
python -c "from config.settings import settings; print(settings.MONGO_URI)"

# Test connection
python -c "from db.connection import get_database; db = get_database(); print(db.command('ping'))"
```

### Telegram Bot Not Responding
```bash
# Verify token format
python -c "from config.settings import settings; print(settings.TELEGRAM_BOT_TOKEN)"

# Check bot status
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

### Pipeline Fails
```bash
# Check logs
tail -f logs/caktykbot_$(date +%Y-%m-%d).log

# Run pipeline manually with debug logging
LOG_LEVEL=DEBUG python main.py fetch
```

### Tests Failing
```bash
# Run specific test with verbose output
pytest tests/test_fetcher.py::test_fetch_ohlcv -vv

# Check coverage
pytest tests/ --cov=. --cov-report=term-missing
```

## 📚 Documentation

- [Sprint 1 Plan (Original)](plan/sprint1_plan.md)
- [Sprint 1 Plan (Revised)](plan/sprint1_plan_REVISED.md)
- [Phase 0-8 Analysis](analysis/)
- [API Documentation](docs/api.md) (coming soon)

## 🤝 Contributing

This is a personal project, but feedback and suggestions are welcome!

## 📄 License

Private project - All rights reserved

## 👤 Author

**Nesa (caktyk)**

---

**Last Updated**: 2026-02-14  
**Sprint**: 1 of 6  
**Status**: Phase 0 Complete ✅
