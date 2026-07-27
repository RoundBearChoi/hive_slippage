# internal_market_to_upbit.py
# Hive internal market (HIVE/HBD) slippage analysis tool
# Focused on converting HBD → HIVE (filling asks)
# Uses beem + CoinGecko reference price
# + Hypothetical Upbit HIVE → KRW sell to derive implied USD/KRW
#
# Refactored to reuse shared logic from hive_orderbook.py
# and selling_on_upbit.py

from hive_orderbook import (
    get_tolerable_slippage,
    connect_to_hive,
    get_reference_price,
    print_internal_snapshot,
    analyze_hbd_to_hive,
)
from selling_on_upbit import (
    convert_hive_to_krw,
    print_orderbook_preview,
    DEFAULT_ORDERBOOK_COUNT,
)

# ------------------- CONFIGURATION -------------------
orderbook_limit = 100          # How many orders to fetch (Hive internal)
top_orders_to_show = 20        # How many levels to display (Hive)
upbit_orderbook_count = DEFAULT_ORDERBOOK_COUNT  # Upbit max supported levels
# ----------------------------------------------------


def main():
    # 1. Ask for tolerable slippage first
    tolerable_slip_pct = get_tolerable_slippage()

    # 2. Connect to Hive
    hive, market = connect_to_hive()

    # 3. CoinGecko reference price
    reference_price, _ = get_reference_price(market)

    # 4. Quick internal market snapshot
    print_internal_snapshot(market, reference_price)

    # 5. Analyze HBD → HIVE on internal market (prints table + summary)
    result = analyze_hbd_to_hive(
        market,
        reference_price,
        tolerable_slip_pct,
        orderbook_limit=orderbook_limit,
        top_orders_to_show=top_orders_to_show,
    )

    max_hbd_within_tolerance = result["max_hbd"]
    max_hive_within_tolerance = result["max_hive"]

    # ----------------------------------------------------
    # 8. Hypothetical: sell the received HIVE on Upbit for KRW
    # ----------------------------------------------------
    if max_hive_within_tolerance > 0:
        print("\n" + "=" * 78)
        print("HYPOTHETICAL: Sell received HIVE on Upbit (KRW-HIVE bids)")
        print("=" * 78)

        try:
            conversion = convert_hive_to_krw(
                max_hive_within_tolerance,
                orderbook_count=upbit_orderbook_count,
            )

            units = conversion["units"]
            krw_received = conversion["krw_received"]
            hive_sold = conversion["hive_filled"]
            levels_used = conversion["levels_used"]
            remaining_hive = conversion["remaining_hive"]
            avg_krw_per_hive = conversion["avg_price"]

            # Show top 10 bid levels for transparency
            print_orderbook_preview(units, asset_name="KRW-HIVE", top_n=10)

            print("\n" + "-" * 70)
            print("Fill simulation against Upbit bids:")
            print(f"  HIVE to sell          : {max_hive_within_tolerance:,.3f}")
            print(f"  HIVE actually filled  : {hive_sold:,.3f}")
            print(f"  Levels consumed       : {levels_used}")

            if remaining_hive > 1e-6:  # floating point tolerance
                print(f"  WARNING: Unfilled     : {remaining_hive:,.3f} HIVE (insufficient depth in top {upbit_orderbook_count} levels)")
                print(f"  KRW received (partial): {krw_received:,.0f} KRW")
            else:
                print(f"  KRW received          : {krw_received:,.0f} KRW")
                print(f"  Average fill price    : {avg_krw_per_hive:,.2f} KRW per HIVE")

            # Derive implied USD/KRW (HBD ≈ 1 USD)
            if max_hbd_within_tolerance > 0 and krw_received > 0:
                implied_usd_krw = krw_received / max_hbd_within_tolerance
                print("\n" + "=" * 78)
                print("IMPLIED EXCHANGE RATE (via this path)")
                print("=" * 78)
                print(f"HBD spent (≈ USD)     : {max_hbd_within_tolerance:,.3f}")
                print(f"KRW received          : {krw_received:,.0f}")
                print(f"Implied 1 USD ≈       : {implied_usd_krw:,.2f} KRW")
                print()

        except Exception as e:
            print(f"Failed to fetch or process Upbit orderbook: {e}")
            print("Skipping KRW conversion step.")


if __name__ == "__main__":
    main()
