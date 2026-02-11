"""
Binary Options Trading Bot — Configuration
All tunable parameters for risk management, signals, and trading.
"""

# ──────────────────────────────────────────────
#  ACCOUNT
# ──────────────────────────────────────────────
INITIAL_BALANCE = 20.0  # Starting simulated balance in USD

# ──────────────────────────────────────────────
#  RISK MANAGEMENT (STRICT)
# ──────────────────────────────────────────────
MAX_RISK_PER_TRADE = 0.02       # 2% of current balance per trade
MAX_DAILY_LOSS = 0.05           # 5% of starting balance — halt trading
MAX_CONSECUTIVE_LOSSES = 3      # Pause after N consecutive losses
COOLDOWN_MINUTES = 10           # Minutes to wait after loss streak
MAX_OPEN_TRADES = 2             # Max simultaneous positions
MIN_BALANCE_RATIO = 0.10        # Stop if balance < 10% of initial

# ──────────────────────────────────────────────
#  TRADE SETTINGS
# ──────────────────────────────────────────────
TRADE_EXPIRY_MINUTES = 5        # Binary option expiry window
PAYOUT_RATE = 0.80              # 80% payout on winning trades
MIN_SIGNAL_CONFIDENCE = 70      # Minimum confidence (0-100) to enter

# ──────────────────────────────────────────────
#  SYMBOLS & TIMEFRAMES
# ──────────────────────────────────────────────
SYMBOLS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "XAU/USD": "GC=F",
}

TIMEFRAMES = ["1m", "5m", "15m"]
PRIMARY_TIMEFRAME = "5m"

# ──────────────────────────────────────────────
#  SIGNAL INDICATOR WEIGHTS
# ──────────────────────────────────────────────
INDICATOR_WEIGHTS = {
    "rsi": 0.20,
    "macd": 0.20,
    "bollinger": 0.15,
    "ema_cross": 0.20,
    "stochastic": 0.15,
    "support_resistance": 0.10,
}

# ──────────────────────────────────────────────
#  RSI SETTINGS
# ──────────────────────────────────────────────
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# ──────────────────────────────────────────────
#  MACD SETTINGS
# ──────────────────────────────────────────────
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ──────────────────────────────────────────────
#  BOLLINGER BANDS
# ──────────────────────────────────────────────
BB_PERIOD = 20
BB_STD_DEV = 2

# ──────────────────────────────────────────────
#  EMA CROSS
# ──────────────────────────────────────────────
EMA_FAST = 9
EMA_SLOW = 21

# ──────────────────────────────────────────────
#  STOCHASTIC
# ──────────────────────────────────────────────
STOCH_K = 14
STOCH_D = 3
STOCH_OVERBOUGHT = 80
STOCH_OVERSOLD = 20

# ──────────────────────────────────────────────
#  SUPPORT / RESISTANCE
# ──────────────────────────────────────────────
SR_LOOKBACK = 50   # Candles to look back for S/R levels
SR_TOLERANCE = 0.0005  # Price proximity tolerance (0.05%)

# ──────────────────────────────────────────────
#  DASHBOARD
# ──────────────────────────────────────────────
REFRESH_INTERVAL_SECONDS = 30
