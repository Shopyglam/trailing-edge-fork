"""
Trading Bot Configuration

Configuration constants for the trailing-edge trading bot including:
- Trading pair settings
- Order constraints and filters
- Fee and buffer settings
- Trailing stop parameters
- Technical indicator configurations
"""

# --- Trading Pair Config ---
SYMBOL = "ETHFDUSD"
BASE_ASSET = "ETH"
QUOTE_ASSET = "FDUSD"

# --- Paper Trading ---
DRY_RUN = False  # Overridden by my_trading_bot/config/strategy_config.py


# --- Filters for constraints (ETHFDUSD) ---
LOT_SIZE = 0.0001  # stepSize for limit orders (LOT_SIZE filter)
MIN_QTY = 0.0001  # minQty (LOT_SIZE filter)
PRICE_TICK = 0.01  # tickSize (PRICE_FILTER)
MIN_PRICE = 0.01  # minPrice (PRICE_FILTER)
MIN_NOTIONAL = 5.0  # minNotional (NOTIONAL filter, applies to market+limit)

# --- Fees and Guard Buffer ---
FEE = 0.0000  # 0.0% fee (Binance spot zero maker fee for ETHFDUSD)
BUFFER = 0.0020  # 0.2% reference value


# --- Trailing Config ---
START_FACTOR = 0.5
MIN_FACTOR = 0.1
GAIN_SCALE_FRAC_BASE = 0.005
GAIN_SCALE_FRAC_QUOTE = 0.005

# --- Dynamic min gain trigger levels ---
MIN_GAIN_TRIGGER_FRAC_BASE = 0.01  # e.g. 0.01 for 1% base asset gain
MIN_GAIN_TRIGGER_FRAC_QUOTE = 0.01  # e.g. 0.01 for 1% quote asset gain

# --- Hard Stop Loss Config ---
HARD_STOP_THRESHOLD_FRAC = 0.005  # e.g. 0.005 for 0.5% static stop loss fallback
# Rationale: Risk 0.5% to make 1%+ = 2:1 reward ratio minimum

# --- Dynamic ATR Volatility Scaling Config ---
DYNAMIC_ATR_ENABLED = True          # Enable ATR-based dynamic risk scaling
ATR_PERIOD = 14                     # 14-period daily ATR (or rolling window)
ATR_MULTIPLIER = 1.5                # Scale factor: Dynamic Stop = 1.5 * ATR_pct
DYNAMIC_STOP_MIN_FRAC = 0.005       # Floor: 0.5% minimum stop loss
DYNAMIC_STOP_MAX_FRAC = 0.050       # Ceiling: 5.0% maximum stop loss

# --- Kline Config ---
KLINE_INTERVAL = "1m"
ROLLING_KLINES_MAXLEN = 1440  # Keep full day of 1m candles

# --- Donchian Config ---
DONCHIAN_WINDOW = 40  # 40 periods (was 20)
DONCHIAN_SHIFT = 2  # 2 periods shift (was 1)
# Rationale: Longer window = smoother channel, less reactive to short-term noise

# --- Donchian Gain Multiplier ---
DONCHIAN_GAIN_MULTIPLIER = 0.5  # Enable Donchian gating (was 0.0)
# Rationale: After hard stop, wait for 50% of Donchian channel width in gain
# before allowing re-entry. Prevents catching falling knives.

# --- Defensive Triad Config ---
POST_HARD_STOP_COOLDOWN_SEC = 3600  # 1 hour static base cooldown after hard stop
DONCHIAN_GATE_CONFIRM_SECONDS = 600  # 10 minutes required confirmation duration (timeframe-independent)
DONCHIAN_GATE_CONFIRM_CANDLES = 10  # Fallback minimum candle count
HARD_STOP_MAX_COUNT = 2             # Circuit breaker threshold count
HARD_STOP_WINDOW_SEC = 86400        # 24 hours window for circuit breaker
HARD_STOP_LOCKOUT_SEC = 43200       # 12 hours static base lockout after circuit breaker
HARD_STOP_CONFIRM_SECONDS = 15      # 15 seconds required confirmation duration below threshold

# --- Dynamic Defensive Triad Adaptation Config ---
DYNAMIC_DEFENSIVE_TRIAD_ENABLED = True  # Enable dynamic adaptation for cooldown, lockout & confirm candles
DYNAMIC_COOLDOWN_MIN_SEC = 300          # 5 minutes floor for flash-wick rebound
DYNAMIC_COOLDOWN_MAX_SEC = 7200         # 2 hours ceiling for cascading drop
DYNAMIC_LOCKOUT_MIN_SEC = 3600          # 1 hour floor for dynamic circuit breaker
DYNAMIC_LOCKOUT_MAX_SEC = 43200         # 12 hours ceiling for extreme turbulence
ALLOW_EARLY_CIRCUIT_BREAKER_UNLOCK = True # Unlock lockout early if market structure flips strongly bullish

# --- Async Loop Config ---
LOOP_SLEEP_SEC = 1.0  # Main async loop sleep duration (in seconds)
