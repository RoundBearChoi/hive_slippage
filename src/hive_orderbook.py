# hive_orderbook.py
# Shared utilities for Hive internal market (HIVE/HBD) orderbook analysis
# Focused on converting HBD → HIVE (filling asks)
# Used by internal_market_to_upbit.py and internal_market_to_binance.py

from beem import Hive
from beem.nodelist import NodeList
from beem.market import Market
import requests

from coingecko_hive_price import get_hive_usd_price


def get_tolerable_slippage():
    """Interactively ask user for tolerable slippage percentage."""
    while True:
        user_input = input("Tolerable slippage %? ").strip()

        if not user_input:
            print("Error: No input provided.")
            continue

        # Allow trailing %
        if user_input.endswith('%'):
            user_input = user_input[:-1]

        try:
            tolerable_slip_pct = float(user_input)
            if tolerable_slip_pct < 0:
                print("Error: Slippage cannot be negative.")
                continue
            break
        except ValueError:
            print("Error: Please enter a valid number (e.g. 1.5 or 2%)")

    print(f"\nUsing tolerable slippage: {tolerable_slip_pct}%")
    return tolerable_slip_pct


def connect_to_hive():
    """Connect to Hive and return (hive, market) for HIVE/HBD.

    Uses a curated list of currently reliable public nodes instead of
    relying solely on NodeList, which can return temporarily dead nodes
    (e.g. api.c0ff33a.uk returning Empty Reply).
    """
    # Curated list of healthy public Hive nodes (ordered by reliability)
    # Updated Aug 2026 — excludes currently dead nodes like api.c0ff33a.uk
    good_nodes = [
        "https://api.hive.blog",
        "https://api.openhive.network",
        "https://rpc.mahdiyari.info",
        "https://api.deathwing.me",
        "https://api.syncad.com",
        "https://techcoderx.com",
        "https://hiveapi.actifit.io",
        "https://hive.atexoras.com:2096",
    ]

    hive = Hive(
        node=good_nodes,
        num_retries=5,          # how many times to try switching nodes
        num_retries_call=3,     # retries per node before switching
        timeout=15,
    )

    # Quick health check + show which node we landed on
    props = hive.get_dynamic_global_properties()
    print("Connected to Hive blockchain")
    print(f"Current block: {props['head_block_number']}")
    print(f"Using node   : {hive.rpc.url}")

    # Internal market: base=HIVE, quote=HBD
    market = Market(base="HIVE", quote="HBD", blockchain_instance=hive)
    return hive, market


def get_reference_price(market):
    """
    Get CoinGecko HIVE/USD as reference (HBD ≈ 1 USD).
    Falls back to internal lowest ask on failure.
    Returns (reference_price, coingecko_hive_usd_or_None)
    """
    print("\n--- CoinGecko Reference ---")
    try:
        hive_usd = get_hive_usd_price()
        reference_price = hive_usd
        print(f"CoinGecko HIVE price : {hive_usd:.6f} USD  (HBD ≈ 1 USD)")
        return reference_price, hive_usd
    except Exception as e:
        print(f"Error fetching CoinGecko: {e}")
        print("Falling back to internal lowest ask as reference.")
        ticker = market.ticker()
        reference_price = float(ticker['lowest_ask'])
        return reference_price, None


def print_internal_snapshot(market, reference_price):
    """Print quick internal market ticker snapshot."""
    ticker = market.ticker()
    lowest_ask = float(ticker['lowest_ask'])
    highest_bid = float(ticker['highest_bid'])
    premium = ((lowest_ask / reference_price) - 1) * 100
    print(f"Internal lowest ask  : {lowest_ask:.6f} HBD/HIVE  ({premium:+.3f}% vs CoinGecko)")
    print(f"Internal highest bid : {highest_bid:.6f} HBD/HIVE")


def analyze_hbd_to_hive(
    market,
    reference_price,
    tolerable_slip_pct,
    orderbook_limit=100,
    top_orders_to_show=20,
):
    """
    Fetch asks, print top levels with cumulative slippage, and compute
    the maximum HBD/HIVE convertible within the tolerable slippage.

    Returns a dict with:
        max_hbd, max_hive, avg_price, actual_slip,
        slippage_hit_index, asks_count
    or None values if no liquidity within tolerance.
    """
    orderbook = market.orderbook(limit=orderbook_limit, raw_data=True)
    asks = orderbook.get('asks', [])

    if not asks:
        print("\nNo asks found on the internal market.")
        return {
            "max_hbd": 0.0,
            "max_hive": 0.0,
            "avg_price": 0.0,
            "actual_slip": 0.0,
            "slippage_hit_index": None,
            "asks_count": 0,
        }

    # ----------------------------------------------------
    # Show top N asks with cumulative HBD + mark slippage point
    # ----------------------------------------------------
    print("\n" + "=" * 78)
    print(f"ASKS (selling HIVE) — Top {top_orders_to_show} levels")
    print("=" * 78)
    print(f"{'#':>3}  {'HIVE':>12}  {'Price':>12}  {'HBD':>12}  {'Cumul HBD':>12}  {'Slip %':>9}")
    print("-" * 78)

    cumulative_hive = 0.0
    cumulative_hbd = 0.0
    slippage_hit_index = None          # first order that exceeds tolerance
    max_hbd_within_tolerance = 0.0
    max_hive_within_tolerance = 0.0

    for idx, order in enumerate(asks[:top_orders_to_show], 1):
        price = float(order['real_price'])
        hive_amt = order['hive'] / 1000.0
        hbd_amt  = order['hbd']  / 1000.0

        # Temporary values if we take this order
        temp_hive = cumulative_hive + hive_amt
        temp_hbd  = cumulative_hbd  + hbd_amt
        temp_avg  = temp_hbd / temp_hive if temp_hive > 0 else price
        temp_slip = ((temp_avg / reference_price) - 1) * 100

        # Check if this order would push us over the limit
        marker = ""
        if slippage_hit_index is None and temp_slip > tolerable_slip_pct:
            slippage_hit_index = idx
            marker = "  <-------"

        # Only accumulate if still within tolerance
        if slippage_hit_index is None:
            cumulative_hive = temp_hive
            cumulative_hbd  = temp_hbd
            max_hbd_within_tolerance  = cumulative_hbd
            max_hive_within_tolerance = cumulative_hive

        print(f"{idx:>3}  {hive_amt:12.3f}  {price:12.6f}  {hbd_amt:12.3f}  {temp_hbd:12.3f}  {temp_slip:+8.3f}%{marker}")

    # If we never hit the limit inside the top N, keep going deeper
    if slippage_hit_index is None:
        for idx, order in enumerate(asks[top_orders_to_show:], top_orders_to_show + 1):
            price = float(order['real_price'])
            hive_amt = order['hive'] / 1000.0
            hbd_amt  = order['hbd']  / 1000.0

            temp_hive = cumulative_hive + hive_amt
            temp_hbd  = cumulative_hbd  + hbd_amt
            temp_avg  = temp_hbd / temp_hive if temp_hive > 0 else price
            temp_slip = ((temp_avg / reference_price) - 1) * 100

            if temp_slip > tolerable_slip_pct:
                slippage_hit_index = idx
                break

            cumulative_hive = temp_hive
            cumulative_hbd  = temp_hbd
            max_hbd_within_tolerance  = cumulative_hbd
            max_hive_within_tolerance = cumulative_hive

    # ----------------------------------------------------
    # Final summary (HBD → HIVE)
    # ----------------------------------------------------
    print("\n" + "=" * 78)
    print("RESULT (HBD → HIVE on Hive internal market)")
    print("=" * 78)

    result = {
        "max_hbd": max_hbd_within_tolerance,
        "max_hive": max_hive_within_tolerance,
        "avg_price": 0.0,
        "actual_slip": 0.0,
        "slippage_hit_index": slippage_hit_index,
        "asks_count": len(asks),
    }

    if max_hbd_within_tolerance > 0:
        avg_price = max_hbd_within_tolerance / max_hive_within_tolerance
        actual_slip = ((avg_price / reference_price) - 1) * 100

        result["avg_price"] = avg_price
        result["actual_slip"] = actual_slip

        print(f"You can convert up to  {max_hbd_within_tolerance:,.3f} HBD")
        print(f"and receive             {max_hive_within_tolerance:,.3f} HIVE")
        print(f"Average fill price    : {avg_price:.6f} HBD per HIVE")
        print(f"Actual slippage       : {actual_slip:+.3f}%  (limit was {tolerable_slip_pct}%)")

        if slippage_hit_index is not None:
            print(f"\nSlippage limit is hit at order #{slippage_hit_index}")
        else:
            print(f"\nAll fetched orders ({len(asks)}) stay within {tolerable_slip_pct}% slippage.")
    else:
        print(f"No liquidity available within {tolerable_slip_pct}% slippage.")
        print("Internal asks are already too expensive vs CoinGecko.")

    return result
