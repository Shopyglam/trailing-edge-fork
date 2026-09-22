import numpy as np
import pytest
from trailingedge.indicators.dynamic_risk import (
    get_dynamic_stop_loss,
    get_dynamic_min_gain,
    get_dynamic_start_factor,
    get_adaptive_donchian_window,
    get_dynamic_cooldown,
    get_dynamic_buffer,
    get_dynamic_lockout,
    check_early_circuit_breaker_unlock,
)


def test_dynamic_stop_loss():
    klines = [{"h": "101.0", "l": "99.0", "c": "100.0"} for _ in range(25)]
    stop = get_dynamic_stop_loss(klines, current_price=100.0, multiplier=1.5)
    assert pytest.approx(stop, abs=0.005) == 0.030


def test_dynamic_min_gain_fee_floor():
    # Fee = 0.1%, Buffer = 0.2% -> Fee floor = 2*0.001 + 0.002 + 0.002 = 0.006 (0.6%)
    klines = [{"h": "100.1", "l": "99.9", "c": "100.0"} for _ in range(25)]
    gain = get_dynamic_min_gain(klines, current_price=100.0, fee=0.001, buffer=0.002)
    assert gain >= 0.006  # Strictly fee profitable


def test_dynamic_start_factor():
    klines = [{"h": "101.0", "l": "99.0", "c": "100.0"} for _ in range(25)]
    factor = get_dynamic_start_factor(klines, current_price=100.0, multiplier=1.0)
    assert pytest.approx(factor, abs=0.005) == 0.020


def test_adaptive_donchian_window():
    assert get_adaptive_donchian_window(adx_val=35) == 20   # Strong trend -> Short window
    assert get_adaptive_donchian_window(adx_val=12) == 80   # Weak chop -> Long window
    assert get_adaptive_donchian_window(adx_val=None) == 40 # Fallback


def test_dynamic_cooldown():
    assert get_dynamic_cooldown(price_drop_1m_pct=0.002) == 300   # Low drop -> 5 min floor
    assert get_dynamic_cooldown(price_drop_1m_pct=0.040) == 7200  # High drop -> 2 hours ceiling


def test_dynamic_buffer():
    # Bid = 100.0, Ask = 100.2 -> Spread = 0.002 (0.2%)
    buf = get_dynamic_buffer(bid=100.0, ask=100.2, safety_margin=0.0005)
    assert pytest.approx(buf, abs=0.0001) == 0.0025


def test_dynamic_lockout():
    klines = [{"h": "101.0", "l": "99.0", "c": "100.0"} for _ in range(25)]
    lockout = get_dynamic_lockout(klines, current_price=100.0, base_lockout_sec=14400)
    assert lockout >= 3600 and lockout <= 43200


def test_check_early_circuit_breaker_unlock():
    # Price reclaimed mid & ADX > 25 -> Should unlock early!
    assert check_early_circuit_breaker_unlock(last_close=105.0, donchian_mid=100.0, adx_val=28) is True
    # Price below mid -> Should NOT unlock
    assert check_early_circuit_breaker_unlock(last_close=98.0, donchian_mid=100.0, adx_val=28) is False
