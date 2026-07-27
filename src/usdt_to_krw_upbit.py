# usdt_to_krw_upbit.py
# Simple interactive tool: sell USDT on Upbit for KRW and derive the
# implied 1 USD ≈ X KRW rate from the fill.
#
# Uses the shared helpers in selling_on_upbit.py

from selling_on_upbit import (
    convert_usdt_to_krw,
    print_orderbook_preview,
    DEFAULT_ORDERBOOK_COUNT,
)

# ------------------- CONFIGURATION -------------------
upbit_orderbook_count = DEFAULT_ORDERBOOK_COUNT  # max 30 levels
# ----------------------------------------------------


def get_usdt_amount() -> float:
    """Interactively ask the user how much USDT to convert."""
    while True:
        user_input = input("How much USDT do you want to convert? ").strip()

        if not user_input:
            print("Error: No input provided.")
            continue

        try:
            amount = float(user_input)
            if amount <= 0:
                print("Error: Amount must be positive.")
                continue
            break
        except ValueError:
            print("Error: Please enter a valid number (e.g. 1000 or 2500.5)")

    print(f"\nConverting {amount:,.4f} USDT → KRW on Upbit")
    return amount


def main():
    # 1. Ask for amount
    usdt_amount = get_usdt_amount()

    # 2. Run simulation
    print("\n" + "=" * 78)
    print("SELL USDT ON UPBIT (KRW-USDT bids)")
    print("=" * 78)

    try:
        conversion = convert_usdt_to_krw(
            usdt_amount,
            orderbook_count=upbit_orderbook_count,
        )

        units = conversion["units"]
        krw_received = conversion["krw_received"]
        usdt_filled = conversion["usdt_filled"]
        levels_used = conversion["levels_used"]
        remaining_usdt = conversion["remaining_usdt"]
        avg_price = conversion["avg_price"]

        # Preview top levels
        print_orderbook_preview(units, asset_name="KRW-USDT", top_n=10)

        # Fill summary
        print("\n" + "-" * 70)
        print("Fill simulation against Upbit bids:")
        print(f"  USDT to sell          : {usdt_amount:,.4f}")
        print(f"  USDT actually filled  : {usdt_filled:,.4f}")
        print(f"  Levels consumed       : {levels_used}")

        if remaining_usdt > 1e-6:
            print(f"  WARNING: Unfilled     : {remaining_usdt:,.4f} USDT "
                  f"(insufficient depth in top {upbit_orderbook_count} levels)")
            print(f"  KRW received (partial): {krw_received:,.0f} KRW")
        else:
            print(f"  KRW received          : {krw_received:,.0f} KRW")
            print(f"  Average fill price    : {avg_price:,.2f} KRW per USDT")

        # Final ratio (USDT treated as exactly 1 USD)
        if usdt_filled > 0 and krw_received > 0:
            implied_usd_krw = krw_received / usdt_filled

            print("\n" + "=" * 78)
            print("RESULT — USDT STARTED vs KRW ENDED")
            print("=" * 78)
            print(f"USDT started with      : {usdt_amount:,.4f} USDT  (treated as exactly 1 USD)")
            print(f"USDT filled            : {usdt_filled:,.4f} USDT")
            print(f"KRW ended with         : {krw_received:,.0f} KRW")
            print(f"Implied 1 USD ≈        : {implied_usd_krw:,.2f} KRW")
            print()

            if remaining_usdt > 1e-6:
                print("(Note: ratio is based only on the filled portion)")
                print()

    except Exception as e:
        print(f"Failed to fetch or process Upbit orderbook: {e}")
        print("Exiting.")


if __name__ == "__main__":
    main()
