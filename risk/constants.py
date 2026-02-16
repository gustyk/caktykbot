"""Constants for Risk Management Domain."""

# Risk Thresholds
MAX_RISK_PER_TRADE = 0.05       # Hard limit 5%
DEFAULT_RISK_PER_TRADE = 0.01   # Default 1%

MAX_PORTFOLIO_HEAT = 0.08       # 8%
HEAT_WARNING_LEVEL = 0.06       # 6%

MAX_EXPOSURE_PER_STOCK = 0.25   # 25%
MAX_SMALL_CAP_EXPOSURE = 0.15   # 15%

MIN_CASH_RESERVE = 0.30         # 30%

# Sector Diversification
MAX_STOCKS_PER_SECTOR = 2

# Correlation
CORRELATION_THRESHOLD = 0.7     # PCC > 0.7 -> Reduce size
CORRELATION_LOOKBACK_DAYS = 90  # 90 trading days

# Circuit Breaker
CB_DRAWDOWN_TRIGGER = 0.10      # 10% drawdown
CB_CONSECUTIVE_LOSS_TRIGGER = 5 # 5 losses
CB_DRAWDOWN_SUSPEND_DAYS = 7
CB_LOSS_SUSPEND_DAYS = 3
CB_REDUCED_RISK = 0.0025        # 0.25% risk after CB

# Validation Messages
MSG_HEAT_LIMIT = "🔴 Heat Limit Reached ({projected:.1%}). Signal blocked."
MSG_SECTOR_LIMIT = "⚠️ Sector limit: Already {count} {sector} stocks open."
MSG_SL_TOO_WIDE = "⚠️ SL too wide ({distance:.1%} > 15%)."
MSG_SL_LOOSENED = "❌ SL cannot be moved lower."
MSG_EXPOSURE_LIMIT = "❌ Exposure {exposure:.1%} exceeds {limit:.1%} max."
MSG_CB_ACTIVE = "🚨 CIRCUIT BREAKER ACTIVATED: {trigger}. Suspended until {until}."
