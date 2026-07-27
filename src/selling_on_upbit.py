# selling_on_upbit.py
# Shared utilities for converting HIVE / USDT to KRW via Upbit orderbooks
# Single source of truth for Upbit-related conversion logic so other scripts
# (e.g. internal_market_to_upbit.py and future tools) stay consistent.
#
# Focus: sell-side simulation against bids (HIVE → KRW, USDT → KRW).
# Fees are ignored for now (same as the rest of the repo).

import requests
from typing import Any, Dict, List, Tuple

# ------------------- CONFIGURATION -------------------
DEFAULT_ORDERBOOK_COUNT = 30   # Upbit max supported levels for /v1/orderbook
UPBIT_ORDERBOOK_URL = "https://api.upbit.com/v1/orderbook"
# ----------------------------------------------------


def fetch_upbit_orderbook(
    markets: str,
    count: int = DEFAULT_ORDERBOOK_COUNT,
    timeout: float = 10.0,
) -> List[Dict[str, Any]]:
    """
    Fetch Upbit orderbook for the given market(s).

    Args:
        markets: e.g. "KRW-HIVE" or "KRW-USDT" (comma-separated for multiple).
        count: Number of orderbook levels (1–30). Defaults to 30.
        timeout: Request timeout in seconds.

    Returns:
        The "orderbook_units" list for the first market in the response.
        Each unit is a dict with keys:
            ask_price, ask_size, bid_price, bid_size (all floats as strings originally).

    Raises:
        requests.RequestException: Network / HTTP errors.
        ValueError: Unexpected response shape or empty orderbook.
    """
    if count < 1 or count > 30:
        raise ValueError("count must be between 1 and 30 (Upbit limit)")

    resp = requests.get(
        UPBIT_ORDERBOOK_URL,
        params={
            "markets": markets,
            "count": count,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    if not data or not isinstance(data, list):
        raise ValueError(f"Unexpected Upbit response format: {data}")

    units = data[0].get("orderbook_units", [])
    if not units:
        raise ValueError(f"No orderbook units returned for {markets}")

    return units


def _simulate_sell_against_bids(
    amount: float,
    units: List[Dict[str, Any]],
) -> Tuple[float, float, int, float]:
    """
    Walk the bid side and fill as much of `amount` as possible.

    Returns:
        (krw_received, amount_filled, levels_used, remaining_amount)
    """
    remaining = float(amount)
    krw = 0.0
    levels = 0

    for u in units:
        if remaining <= 0:
            break

        bid_price = float(u["bid_price"])
        bid_size = float(u["bid_size"])

        take = min(remaining, bid_size)
        krw += take * bid_price
        remaining -= take
        levels += 1

    filled = float(amount) - remaining
    return krw, filled, levels, remaining


def convert_hive_to_krw(
    hive_amount: float,
    orderbook_count: int = DEFAULT_ORDERBOOK_COUNT,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """
    Simulate selling `hive_amount` HIVE on Upbit (KRW-HIVE bids).

    Args:
        hive_amount: Quantity of HIVE to sell.
        orderbook_count: Depth levels to fetch (max 30).
        timeout: HTTP timeout.

    Returns:
        dict with keys:
            krw_received   (float)  – total KRW obtained
            hive_filled    (float)  – how much HIVE was actually filled
            avg_price      (float)  – average fill price in KRW per HIVE (0 if none)
            levels_used    (int)    – number of bid levels consumed
            remaining_hive (float)  – unfilled portion (if any)
            units          (list)   – the raw orderbook_units used (for callers that want to print levels)

    Raises:
        ValueError / requests.RequestException on fetch or empty book.
    """
    if hive_amount <= 0:
        return {
            "krw_received": 0.0,
            "hive_filled": 0.0,
            "avg_price": 0.0,
            "levels_used": 0,
            "remaining_hive": 0.0,
            "units": [],
        }

    units = fetch_upbit_orderbook("KRW-HIVE", count=orderbook_count, timeout=timeout)
    krw_received, hive_filled, levels_used, remaining = _simulate_sell_against_bids(
        hive_amount, units
    )

    avg_price = krw_received / hive_filled if hive_filled > 0 else 0.0

    return {
        "krw_received": krw_received,
        "hive_filled": hive_filled,
        "avg_price": avg_price,
        "levels_used": levels_used,
        "remaining_hive": remaining,
        "units": units,
    }


def convert_usdt_to_krw(
    usdt_amount: float,
    orderbook_count: int = DEFAULT_ORDERBOOK_COUNT,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """
    Simulate selling `usdt_amount` USDT on Upbit (KRW-USDT bids).

    Args:
        usdt_amount: Quantity of USDT to sell.
        orderbook_count: Depth levels to fetch (max 30).
        timeout: HTTP timeout.

    Returns:
        dict with keys:
            krw_received   (float)  – total KRW obtained
            usdt_filled    (float)  – how much USDT was actually filled
            avg_price      (float)  – average fill price in KRW per USDT (0 if none)
            levels_used    (int)    – number of bid levels consumed
            remaining_usdt (float)  – unfilled portion (if any)
            units          (list)   – the raw orderbook_units used

    Raises:
        ValueError / requests.RequestException on fetch or empty book.
    """
    if usdt_amount <= 0:
        return {
            "krw_received": 0.0,
            "usdt_filled": 0.0,
            "avg_price": 0.0,
            "levels_used": 0,
            "remaining_usdt": 0.0,
            "units": [],
        }

    units = fetch_upbit_orderbook("KRW-USDT", count=orderbook_count, timeout=timeout)
    krw_received, usdt_filled, levels_used, remaining = _simulate_sell_against_bids(
        usdt_amount, units
    )

    avg_price = krw_received / usdt_filled if usdt_filled > 0 else 0.0

    return {
        "krw_received": krw_received,
        "usdt_filled": usdt_filled,
        "avg_price": avg_price,
        "levels_used": levels_used,
        "remaining_usdt": remaining,
        "units": units,
    }


def print_orderbook_preview(
    units: List[Dict[str, Any]],
    asset_name: str = "ASSET",
    top_n: int = 10,
) -> None:
    """
    Convenience helper to print top bid levels (same format used in the rest of the repo).
    Callers can use this after convert_* if they want the visual table.
    """
    print(f"\nUpbit top bid levels for {asset_name} (best first):")
    print(f"{'#':>3}  {'Bid Price':>12}  {'Bid Size':>16}  {'Cumul':>12}  {'Cumul KRW':>14}")
    print("-" * 70)

    cum_size = 0.0
    cum_krw = 0.0
    for i, u in enumerate(units[:top_n], 1):
        bp = float(u["bid_price"])
        bs = float(u["bid_size"])
        cum_size += bs
        cum_krw += bp * bs
        print(f"{i:>3}  {bp:12.1f}  {bs:16.4f}  {cum_size:12.3f}  {cum_krw:14,.0f}")
