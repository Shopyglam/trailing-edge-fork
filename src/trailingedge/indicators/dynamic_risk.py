"""
Dynamic Risk & Execution Parameter Adaptation Engine

Provides volatility, momentum, velocity, and orderbook-adaptive dynamic parameter calculations:
1. Dynamic Hard Stop Loss (ATR-scaled)
2. Dynamic Minimum Profit Target (ATR & Fee-scaled)
3. Dynamic Trailing Callback Factor (ATR-scaled)
4. Adaptive Donchian Lookback Window (ADX/Volatility-scaled)
5. Dynamic Velocity-Based Cooldown
6. Live Orderbook Spread Buffer
7. Dynamic Circuit Breaker Hard Lockout & Early Unlock
"""

import numpy as np
import pandas as pd
from trailingedge.indicators.atr import compute_atr


def get_dynamic_stop_loss(
    klines,
    current_price: float,
    multiplier: float = 1.5,
    min_stop: float = 0.005,
    max_stop: float = 0.050,
    period: int = 14,
    row_format: str = "dict",
    static_fallback: float = 0.005,
) -> float:
    """Compute dynamic ATR-scaled hard stop loss fraction."""
    if not klines or current_price is None or current_price <= 0:
        return static_fallback
    atr_val = compute_atr(
        klines, period=period, method="wilder", row_format=row_format, return_series=False
    )
    if atr_val is None or atr_val <= 0:
        return static_fallback
    raw_stop = (atr_val / float(current_price)) * float(multiplier)
    return float(np.clip(raw_stop, min_stop, max_stop))


def get_dynamic_min_gain(
    klines,
    current_price: float,
    fee: float = 0.001,
    buffer: float = 0.002,
    multiplier: float = 1.2,
    min_gain: float = 0.006,
    max_gain: float = 0.050,
    period: int = 14,
    row_format: str = "dict",
    static_fallback: float = 0.010,
) -> float:
    """
    Compute dynamic profit target based on ATR volatility.
    Guarantees target stays above (FEE * 2 + BUFFER + 0.2%) to preserve net profitability.
    """
    fee_floor = (fee * 2.0) + buffer + 0.002
    effective_min = max(min_gain, fee_floor)

    if not klines or current_price is None or current_price <= 0:
        return max(static_fallback, effective_min)

    atr_val = compute_atr(
        klines, period=period, method="wilder", row_format=row_format, return_series=False
    )
    if atr_val is None or atr_val <= 0:
        return max(static_fallback, effective_min)

    raw_gain = (atr_val / float(current_price)) * float(multiplier)
    return float(np.clip(raw_gain, effective_min, max_gain))


def get_dynamic_start_factor(
    klines,
    current_price: float,
    multiplier: float = 1.0,
    min_factor: float = 0.003,
    max_factor: float = 0.020,
    period: int = 14,
    row_format: str = "dict",
    static_fallback: float = 0.005,
) -> float:
    """Compute dynamic initial trailing callback factor based on ATR volatility."""
    if not klines or current_price is None or current_price <= 0:
        return static_fallback
    atr_val = compute_atr(
        klines, period=period, method="wilder", row_format=row_format, return_series=False
    )
    if atr_val is None or atr_val <= 0:
        return static_fallback
    raw_factor = (atr_val / float(current_price)) * float(multiplier)
    return float(np.clip(raw_factor, min_factor, max_factor))


def get_adaptive_donchian_window(
    adx_val: float | None = None,
    base_window: int = 40,
    min_window: int = 20,
    max_window: int = 80,
    static_fallback: int = 40,
) -> int:
    """
    Adapt Donchian lookback window based on ADX trend strength:
    - ADX >= 30 (Strong Trend): Shorten window (20) for rapid pullback re-entry.
    - ADX <= 18 (Weak Chop): Expand window (80) to filter out fake breakouts.
    """
    if adx_val is None or np.isnan(adx_val):
        return static_fallback
    if adx_val >= 30:
        return min_window
    elif adx_val <= 18:
        return max_window
    else:
        # Linear interpolation between 18 (max_window) and 30 (min_window)
        ratio = (30.0 - float(adx_val)) / (30.0 - 18.0)
        return int(min_window + ratio * (max_window - min_window))


def get_dynamic_cooldown(
    price_drop_1m_pct: float = 0.0,
    base_cooldown_sec: int = 1800,
    max_cooldown_sec: int = 7200,
    min_cooldown_sec: int = 300,
) -> int:
    """
    Dynamically scale post-hard-stop cooldown based on 1-minute drop velocity.
    - Cascading crash (>3.0% drop in 1 min): Lockout scales up to 2 hours.
    - Minor stop breach (<0.5% drop): Short 5-minute cooldown.
    """
    abs_drop = abs(price_drop_1m_pct)
    if abs_drop <= 0.005:
        return min_cooldown_sec
    elif abs_drop >= 0.030:
        return max_cooldown_sec
    else:
        ratio = (abs_drop - 0.005) / (0.030 - 0.005)
        return int(min_cooldown_sec + ratio * (max_cooldown_sec - min_cooldown_sec))


def get_dynamic_buffer(
    bid: float | None,
    ask: float | None,
    min_buffer: float = 0.001,
    max_buffer: float = 0.010,
    safety_margin: float = 0.0005,
    static_fallback: float = 0.002,
) -> float:
    """Compute live orderbook spread buffer based on bid-ask spread."""
    if bid is None or ask is None or bid <= 0:
        return static_fallback
    spread_frac = (ask - bid) / bid
    return float(np.clip(spread_frac + safety_margin, min_buffer, max_buffer))


def get_dynamic_lockout(
    klines,
    current_price: float,
    base_lockout_sec: int = 14400,
    min_lockout_sec: int = 3600,
    max_lockout_sec: int = 43200,
    baseline_atr_pct: float = 0.015,
    period: int = 14,
    row_format: str = "dict",
) -> int:
    """
    Dynamically scale circuit breaker hard lockout based on current market volatility ratio.
    """
    if not klines or current_price is None or current_price <= 0:
        return base_lockout_sec
    atr_val = compute_atr(
        klines, period=period, method="wilder", row_format=row_format, return_series=False
    )
    if atr_val is None or atr_val <= 0:
        return base_lockout_sec

    current_atr_pct = atr_val / float(current_price)
    vol_ratio = current_atr_pct / float(baseline_atr_pct) if baseline_atr_pct > 0 else 1.0
    scaled_lockout = int(base_lockout_sec * vol_ratio)
    return int(np.clip(scaled_lockout, min_lockout_sec, max_lockout_sec))


def check_early_circuit_breaker_unlock(
    last_close: float,
    donchian_mid: float,
    adx_val: float | None = None,
    rsi_val: float | None = None,
) -> bool:
    """
    Check if market conditions qualify for early circuit breaker lockout unlock:
    - Price reclaimed upper Donchian mid-line AND
    - Strong momentum (ADX > 25) or Oversold Recovery (RSI > 45)
    """
    if last_close is None or donchian_mid is None or donchian_mid <= 0:
        return False
    price_reclaimed = last_close > donchian_mid
    momentum_valid = (adx_val is not None and adx_val >= 25) or (rsi_val is not None and rsi_val >= 45)
    return price_reclaimed and momentum_valid
