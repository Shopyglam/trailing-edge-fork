"""
Binance Spot order placement utilities via WebSocket API.

Handles limit, market, OCO orders and mass-cancel operations.
Includes realistic paper trading balance and fill updates for DRY_RUN mode.
"""

import json
import uuid

from trailingedge.auth.manager import get_server_timestamp
from trailingedge.config import DRY_RUN
from my_trading_bot.dashboard_server import broadcast_event


def process_dry_run_fill(side, price, qty, symbol, account_snapshot=None, state=None, fee_rate=0.001):
    """Executes a realistic paper fill, updating balances, fees, and state flags in DRY_RUN mode."""
    if account_snapshot is None:
        broadcast_event("marker", {"side": side, "type": "LIMIT_MAKER", "price": float(price), "qty": float(qty), "symbol": symbol})
        return

    base_asset = "BTC" if "BTC" in symbol else symbol[:3]
    quote_asset = "USDT" if "USDT" in symbol else "FDUSD" if "FDUSD" in symbol else symbol[3:]

    price = float(price)
    qty = float(qty)

    if side == "BUY":
        usdt_free = account_snapshot.get(quote_asset, {}).get("free", 0.0)
        if usdt_free <= 0:
            return
        gross_cost = qty * price
        actual_spend = min(gross_cost, usdt_free)
        if actual_spend <= 0:
            return
        
        fee_paid = actual_spend * fee_rate
        net_spend = actual_spend - fee_paid
        btc_bought = net_spend / price if price > 0 else 0.0

        account_snapshot[quote_asset]["free"] = max(0.0, usdt_free - actual_spend)
        account_snapshot[quote_asset]["total"] = account_snapshot[quote_asset]["free"]

        account_snapshot.setdefault(base_asset, {"free": 0.0, "locked": 0.0, "total": 0.0})
        account_snapshot[base_asset]["free"] += btc_bought
        account_snapshot[base_asset]["total"] = account_snapshot[base_asset]["free"]

        if state is not None:
            state.maker_exit_armed = False
            state.hard_stop_armed = False

        print(f"\n[PAPER FILL] 🟢 BOUGHT {btc_bought:.6f} {base_asset} @ ${price:.2f} | Spent ${actual_spend:.2f} {quote_asset} (Fee: ${fee_paid:.2f}) | New Balances: {account_snapshot[base_asset]['free']:.6f} {base_asset} / ${account_snapshot[quote_asset]['free']:.2f} {quote_asset}\n")
        broadcast_event("marker", {"side": "BUY", "type": "LIMIT_MAKER", "price": price, "qty": btc_bought, "symbol": symbol})

    elif side == "SELL":
        btc_free = account_snapshot.get(base_asset, {}).get("free", 0.0)
        if btc_free <= 0:
            return
        actual_qty_sold = min(qty, btc_free)
        if actual_qty_sold <= 0:
            return

        gross_usdt = actual_qty_sold * price
        fee_paid = gross_usdt * fee_rate
        net_usdt = gross_usdt - fee_paid

        account_snapshot[base_asset]["free"] = max(0.0, btc_free - actual_qty_sold)
        account_snapshot[base_asset]["total"] = account_snapshot[base_asset]["free"]

        account_snapshot.setdefault(quote_asset, {"free": 0.0, "locked": 0.0, "total": 0.0})
        account_snapshot[quote_asset]["free"] += net_usdt
        account_snapshot[quote_asset]["total"] = account_snapshot[quote_asset]["free"]

        if state is not None:
            state.maker_exit_armed = False
            state.hard_stop_armed = False

        print(f"\n[PAPER FILL] 🔴 SOLD {actual_qty_sold:.6f} {base_asset} @ ${price:.2f} | Received ${net_usdt:.2f} {quote_asset} (Fee: ${fee_paid:.2f}) | New Balances: {account_snapshot[base_asset]['free']:.6f} {base_asset} / ${account_snapshot[quote_asset]['free']:.2f} {quote_asset}\n")
        broadcast_event("marker", {"side": "SELL", "type": "LIMIT_MAKER", "price": price, "qty": actual_qty_sold, "symbol": symbol})


async def place_limit_order(ws, symbol, side, price, qty, clientOrderId=None, account_snapshot=None, state=None):
    """Place a limit order."""
    if clientOrderId is None:
        clientOrderId = str(uuid.uuid4())
    payload = {
        "id": "order_place",
        "method": "order.place",
        "params": {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "price": f"{price:.8f}",
            "quantity": f"{qty:.8f}",
            "newClientOrderId": clientOrderId,
            "timestamp": get_server_timestamp(),
        },
    }
    if DRY_RUN:
        print(f"\n[DRY RUN] 🟢 Simulated LIMIT {side} order for {qty} {symbol} at {price}\n")
        process_dry_run_fill(side, price, qty, symbol, account_snapshot, state)
        return clientOrderId
    await ws.send(json.dumps(payload))
    return clientOrderId


async def place_market_order(ws, symbol, side, qty, clientOrderId=None, account_snapshot=None, state=None, price=None):
    """Place a market order."""
    if clientOrderId is None:
        clientOrderId = str(uuid.uuid4())
    payload = {
        "id": "order_place_market",
        "method": "order.place",
        "params": {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": f"{qty:.8f}",
            "newClientOrderId": clientOrderId,
            "timestamp": get_server_timestamp(),
        },
    }
    if DRY_RUN:
        print(f"\n[DRY RUN] 🟢 Simulated MARKET {side} order for {qty} {symbol}\n")
        fill_price = price if price is not None else 0.0
        process_dry_run_fill(side, fill_price, qty, symbol, account_snapshot, state)
        return clientOrderId
    await ws.send(json.dumps(payload))
    return clientOrderId


async def cancel_all_orders(ws, symbol="BTCFDUSD"):
    """Cancel all open orders for a symbol."""
    payload = {
        "id": "cancel_all",
        "method": "openOrders.cancelAll",
        "params": {"symbol": symbol, "timestamp": get_server_timestamp()},
    }
    if DRY_RUN:
        print(f"\n[DRY RUN] 🛑 Simulated CANCEL ALL orders for {symbol}\n")
        return
    await ws.send(json.dumps(payload))


async def query_order_status(ws, symbol, origClientOrderId):
    """Query order status using WebSocket API."""
    payload = {
        "id": f"status_{origClientOrderId}",
        "method": "order.status",
        "params": {
            "symbol": symbol,
            "origClientOrderId": origClientOrderId,
            "timestamp": get_server_timestamp()
        }
    }
    if DRY_RUN:
        return
    await ws.send(json.dumps(payload))


async def place_oco_order(ws, symbol, side, quantity, limit_price, stop_price, account_snapshot=None, state=None):
    """Place an OCO order."""
    payload = {
        "id": str(uuid.uuid4()),
        "method": "orderList.place.oco",
        "params": {
            "symbol": symbol,
            "side": side,
            "quantity": float(quantity),
            "aboveType": "LIMIT_MAKER",
            "abovePrice": f"{limit_price:.8f}",
            "aboveTimeInForce": "GTC",
            "belowType": "STOP_LOSS",
            "belowStopPrice": f"{stop_price:.8f}",
            "timestamp": get_server_timestamp(),
        },
    }
    if DRY_RUN:
        print(f"\n[DRY RUN] 🟢 Simulated OCO {side} order for {quantity} {symbol}\n")
        process_dry_run_fill(side, limit_price, quantity, symbol, account_snapshot, state)
        return
    await ws.send(json.dumps(payload))


async def order_replace(ws, symbol, side, price, qty, clientOrderId, origClientOrderId, account_snapshot=None, state=None):
    """Stateless cancel+replace LIMIT_MAKER order via WebSocket v3."""
    payload = {
        "id": clientOrderId,
        "method": "order.cancelReplace",
        "params": {
            "symbol": symbol,
            "cancelReplaceMode": "ALLOW_FAILURE",
            "cancelOrigClientOrderId": origClientOrderId,
            "side": side,
            "type": "LIMIT_MAKER",
            "price": f"{price:.8f}",
            "quantity": f"{qty:.8f}",
            "newClientOrderId": clientOrderId,
            "timestamp": get_server_timestamp(),
        },
    }
    if DRY_RUN:
        print(f"\n[DRY RUN] 🔄 Simulated ORDER REPLACE (LIMIT_MAKER) {side} for {qty} {symbol} at {price}\n")
        process_dry_run_fill(side, price, qty, symbol, account_snapshot, state)
        return
    await ws.send(json.dumps(payload))

