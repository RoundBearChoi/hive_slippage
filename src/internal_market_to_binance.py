# internal_market_to_binance.py
# Hive internal market (HIVE/HBD) + Binance HIVE/USDT slippage analysis
# Path: HBD → HIVE (internal market) → USDT (Binance bids)
# Reports overall % loss from starting HBD to ending USDT (treated as path slippage)
# Fees are ignored for now.

from hive_orderbook import (
    get_tolerable_slippage,
    connect_to_hive,
    get_reference_price,
    print_internal_snapshot,
    analyze_hbd_to_hive,
)
import requests

# ------------------- CONFIGURATION -------------------
orderbook_limit = 100          # How many orders to fetch (Hive internal)
top_orders_to_show = 20        # How many levels to display (Hive)
binance_orderbook_limit = 100  # Binance depth levels (max 5000, 100 is plenty for most sizes)
# ----------------------------------------------------


def fetch_binance_hive_usdt_orderbook(limit=100):
    """
    Fetch Binance HIVEUSDT order book (depth).
    Returns the 'bids' list (highest price first) or raises.
    """
    url = "https://api.binance.com/api/v3/depth"
    params = {
        "symbol": "HIVEUSDT",
        "limit": limit,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    bids = data.get("bids", [])
    if not bids:
        raise ValueError("No bids returned from Binance HIVEUSDT orderbook")
    return bids


def simulate_sell_hive_on_binance(hive_amount, bids):
    """
    Walk the bid side and fill as much of `hive_amount` as possible.
    Returns (usdt_received, hive_filled, levels_used, remaining_hive)
    """
    remaining = hive_amount
    usdt = 0.0
    levels = 0

    for price_str, qty_str in bids:
        if remaining <= 0:
            break
        price = float(price_str)
        qty = float(qty_str)

        take = min(remaining, qty)
        usdt += take * price
        remaining -= take
        levels += 1

    filled = hive_amount - remaining
    return usdt, filled, levels, remaining


def main():
    # 1. Tolerable slippage (applies to the internal HBD→HIVE leg)
    tolerable_slip_pct = get_tolerable_slippage()

    # 2. Connect to Hive
    hive, market = connect_to_hive()

    # 3. Reference price
    reference_price, _ = get_reference_price(market)

    # 4. Quick internal snapshot
    print_internal_snapshot(market, reference_price)

    # 5. Analyze HBD → HIVE on internal market
    result = analyze_hbd_to_hive(
        market,
        reference_price,
        tolerable_slip_pct,
        orderbook_limit=orderbook_limit,
        top_orders_to_show=top_orders_to_show,
    )

    max_hbd = result["max_hbd"]
    max_hive = result["max_hive"]

    if max_hive <= 0:
        print("\nNothing to sell on Binance — exiting.")
        return

    # ----------------------------------------------------
    # 6. Hypothetical: sell the received HIVE on Binance for USDT
    # ----------------------------------------------------
    print("\n" + "=" * 78)
    print("HYPOTHETICAL: Sell received HIVE on Binance (HIVEUSDT bids)")
    print("=" * 78)

    try:
        bids = fetch_binance_hive_usdt_orderbook(limit=binance_orderbook_limit)

        # Preview top 10 bid levels
        print(f"\nBinance HIVEUSDT top bid levels (best first):")
        print(f"{'#':>3}  {'Bid Price':>12}  {'Bid Size (HIVE)':>16}  {'Cumul HIVE':>12}  {'Cumul USDT':>14}")
        print("-" * 70)

        preview_cum_hive = 0.0
        preview_cum_usdt = 0.0
        for i, (price_str, qty_str) in enumerate(bids[:10], 1):
            bp = float(price_str)
            bs = float(qty_str)
            preview_cum_hive += bs
            preview_cum_usdt += bp * bs
            print(f"{i:>3}  {bp:12.6f}  {bs:16.4f}  {preview_cum_hive:12.3f}  {preview_cum_usdt:14,.4f}")

        # Simulate full fill of the HIVE we obtained
        usdt_received, hive_sold, levels_used, remaining_hive = simulate_sell_hive_on_binance(
            max_hive, bids
        )

        print("\n" + "-" * 70)
        print("Fill simulation against Binance bids:")
        print(f"  HIVE to sell          : {max_hive:,.3f}")
        print(f"  HIVE actually filled  : {hive_sold:,.3f}")
        print(f"  Levels consumed       : {levels_used}")

        if remaining_hive > 1e-6:
            print(f"  WARNING: Unfilled     : {remaining_hive:,.3f} HIVE (insufficient depth in top {binance_orderbook_limit} levels)")
            print(f"  USDT received (partial): {usdt_received:,.4f} USDT")
        else:
            avg_usdt_per_hive = usdt_received / hive_sold if hive_sold > 0 else 0.0
            print(f"  USDT received          : {usdt_received:,.4f} USDT")
            print(f"  Average fill price    : {avg_usdt_per_hive:.6f} USDT per HIVE")

        # ----------------------------------------------------
        # 7. Overall path: HBD start → USDT end  (treat % difference as slippage)
        # ----------------------------------------------------
        if max_hbd > 0 and usdt_received > 0:
            # Because HBD ≈ 1 USD and USDT ≈ 1 USD, the ratio directly shows
            # the combined effect of internal-market premium + Binance impact.
            loss_pct = ((max_hbd - usdt_received) / max_hbd) * 100 * -1
            recovery_ratio = usdt_received / max_hbd

            print("\n" + "=" * 78)
            print("OVERALL PATH RESULT (HBD → HIVE → USDT)")
            print("=" * 78)
            print(f"HBD started with       : {max_hbd:,.3f} HBD  (≈ USD)")
            print(f"USDT ended with        : {usdt_received:,.4f} USDT")
            print(f"Recovery ratio         : {recovery_ratio:.6f}  (USDT / HBD)")
            print(f"Overall % loss         : {loss_pct:+.3f}%")
            print()

    except Exception as e:
        print(f"Failed to fetch or process Binance orderbook: {e}")
        print("Skipping USDT conversion step.")


if __name__ == "__main__":
    main()
