"""
Binance Spot WebSocket User Data Stream Utility

Parses outboundAccountPosition (balance update) and updates a shared dict.
"""

import asyncio
import json
from datetime import datetime

import websockets

from trailingedge.auth.manager import send_session_logon

WS_URL = "wss://ws-api.binance.com:443/ws-api/v3"

# --- Test Config (for __main__ only) ---
BASE_ASSET = "BTC"
QUOTE_ASSET = "FDUSD"


def now():
    """Return current local time for logs, always in YYYY-MM-DD HH:MM:SS."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def account_ws_receiver(ws, snapshot_dict, order_snapshot_dict=None, pending_requests=None):
    """
    Listens for WS messages and updates snapshot_dict for balance changes.
    Also updates order_snapshot_dict for execution reports.
    Resolves pending_requests futures for API responses.
    Never breaks on error; always continues unless ws is closed.
    """
    if order_snapshot_dict is None:
        order_snapshot_dict = {}
    if pending_requests is None:
        pending_requests = {}

    while True:
        try:
            msg = await ws.recv()
            
            # Try to parse as an event first
            is_balance = parse_account_balance_event(msg, snapshot_dict)
            is_exec = parse_execution_report_event(msg, order_snapshot_dict)
            
            # If not an event, check if it's an API response
            if not is_balance and not is_exec:
                data = json.loads(msg)
                if isinstance(data, dict) and "id" in data:
                    req_id = data["id"]
                    if req_id in pending_requests:
                        future = pending_requests.pop(req_id)
                        if not future.done():
                            if "error" in data:
                                future.set_exception(Exception(data["error"]))
                            else:
                                future.set_result(data.get("result", data))

        except websockets.exceptions.ConnectionClosed:
            print(
                f"[{now()}] [ERROR] WS connection closed in account_ws_receiver, exiting loop."
            )
            break  # <-- Break ONLY on true disconnection!
        except Exception as e:
            print(f"[{now()}] [ERROR] in account_ws_receiver: {e}")
            continue  # <-- Continue for all other (parsing/noise) errors


def parse_account_balance_event(message: str, snapshot_dict: dict) -> bool:
    """
    Parse account balance update event and update snapshot dictionary.
    Returns True if successfully parsed, False otherwise.
    """
    try:
        data = json.loads(message)
        # Defensive parse: skip if not a dict or missing expected keys
        if not isinstance(data, dict):
            return False
        if "event" in data:
            data = data["event"]
        # Only process if it's the right event type
        if data.get("e") == "outboundAccountPosition":
            for entry in data.get("B", []):
                asset = entry["a"]
                free = float(entry["f"])
                locked = float(entry["l"])
                snapshot_dict[asset] = {
                    "free": free,
                    "locked": locked,
                    "total": free + locked,
                }
            return True
        # Not an account update event
        return False
    except Exception:
        # Instead of spamming, you can log once, or suppress completely
        # print(f"[{now()}] Non-account message skipped: {e}")
        return False


def parse_execution_report_event(message: str, order_snapshot_dict: dict) -> bool:
    """
    Parse executionReport event and update order_snapshot_dict.
    Returns True if successfully parsed, False otherwise.
    """
    try:
        data = json.loads(message)
        if not isinstance(data, dict):
            return False
        if "event" in data:
            data = data["event"]
            
        if data.get("e") == "executionReport":
            client_id = data.get("c")
            if client_id:
                order_snapshot_dict[client_id] = {
                    "orderId": data.get("i"),
                    "clientOrderId": client_id,
                    "status": data.get("X"),
                    "side": data.get("S"),
                    "type": data.get("o"),
                    "filled_qty": float(data.get("z", 0.0)),
                    "total_qty": float(data.get("q", 0.0)),
                    "quote_qty_filled": float(data.get("Z", 0.0)),
                    "commission": float(data.get("n", 0.0)),
                    "commission_asset": data.get("N"),
                    "last_fill_qty": float(data.get("l", 0.0)),
                    "last_fill_price": float(data.get("L", 0.0)),
                    "timestamp": data.get("E")
                }
            return True
        return False
    except Exception:
        return False


def get_balance_from_snapshot(
    snapshot_dict: dict, base_asset: str, quote_asset: str
) -> dict[str, dict[str, float]]:
    """
    Returns dict with 'free', 'locked', and 'total' balances for both assets.
    Structure:
    {
        "free":   {BASE: float, QUOTE: float},
        "locked": {BASE: float, QUOTE: float},
        "total":  {BASE: float, QUOTE: float}
    }
    """

    def extract(asset):
        free = snapshot_dict.get(asset, {}).get("free", 0.0)
        total = snapshot_dict.get(asset, {}).get("total", 0.0)
        locked = max(0.0, total - free)
        return free, locked, total

    base_free, base_locked, base_total = extract(base_asset)
    quote_free, quote_locked, quote_total = extract(quote_asset)

    return {
        "free": {base_asset: base_free, quote_asset: quote_free},
        "locked": {base_asset: base_locked, quote_asset: quote_locked},
        "total": {base_asset: base_total, quote_asset: quote_total},
    }


if __name__ == "__main__":

    async def main():
        snapshot = {}
        print(f"[{now()}] Starting test WebSocket session for account balance...")

        async with websockets.connect(WS_URL) as ws:
            await send_session_logon(ws)
            print(f"[{now()}] ✅ Authenticated.")
            await ws.send(
                json.dumps({"method": "userDataStream.subscribe", "id": 10001})
            )
            print(f"[{now()}] ✅ Subscribed to userDataStream.")

            # Launch the receiver as a background task
            order_snapshot = {}
            asyncio.create_task(account_ws_receiver(ws, snapshot, order_snapshot))

            while True:
                reduced = get_balance_from_snapshot(snapshot, BASE_ASSET, QUOTE_ASSET)
                # Raw output for debug/logging:
                print(f"[{now()}] Reduced snapshot: {reduced}")
                await asyncio.sleep(1.0)

    asyncio.run(main())
