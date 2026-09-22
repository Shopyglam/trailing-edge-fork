import numpy as np
import pytest
from trailingedge.indicators.atr import compute_atr, get_dynamic_stop_loss


def test_get_dynamic_stop_loss_basic():
    # Construct 25 synthetic klines with $2 true range ($100 price, $2 range = 2% volatility)
    klines = []
    for i in range(25):
        klines.append({"h": "101.0", "l": "99.0", "c": "100.0"})

    # 2% volatility * 1.5 multiplier = 3.0% dynamic stop loss
    dynamic_stop = get_dynamic_stop_loss(
        klines,
        current_price=100.0,
        multiplier=1.5,
        min_stop=0.005,
        max_stop=0.050,
        period=14,
    )

    assert pytest.approx(dynamic_stop, abs=0.005) == 0.030


def test_get_dynamic_stop_loss_clamping():
    # Low volatility: $0.10 range on $100 price = 0.1% volatility
    low_vol_klines = [{"h": "100.1", "l": "99.9", "c": "100.0"} for _ in range(25)]
    floor_stop = get_dynamic_stop_loss(
        low_vol_klines, current_price=100.0, min_stop=0.005
    )
    assert floor_stop == 0.005  # Clamped to min floor

    # High volatility: $20 range on $100 price = 20% volatility
    high_vol_klines = [{"h": "110.0", "l": "90.0", "c": "100.0"} for _ in range(25)]
    ceiling_stop = get_dynamic_stop_loss(
        high_vol_klines, current_price=100.0, max_stop=0.050
    )
    assert ceiling_stop == 0.050  # Clamped to max ceiling
