# fromGecko.py
# Hive internal market (HIVE/HBD) slippage analysis tool
# Focused on converting HBD → HIVE (filling asks)
# Uses beem + CoinGecko reference price
# + Hypothetical Upbit HIVE → KRW sell to derive implied USD/KRW

from beem import Hive
from beem.nodelist import NodeList
from beem.market import Market
import requests

# ------------------- CONFIGURATION -------------------
orderbook_limit = 100          # How many orders to fetch (Hive internal)
top_orders_to_show = 20        # How many levels to display (Hive)
upbit_orderbook_count = 30     # Upbit max supported levels
# ----------------------------------------------------

# 1. Ask for tolerable slippage first
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

# 2. Connect to Hive
nodelist = NodeList()
nodelist.update_nodes()
hive_nodes = nodelist.get_hive_nodes()
hive = Hive(node=hive_nodes)
print("Connected to Hive blockchain")
print("Current block:", hive.get_dynamic_global_properties()['head_block_number'])

# Internal market: base=HIVE, quote=HBD
market = Market(base="HIVE", quote="HBD", blockchain_instance=hive)

# 3. CoinGecko reference price
print("\n--- CoinGecko Reference ---")
try:
    response = requests.get(
        "https://api.coingecko.com/api/v3/simple/price?ids=hive&vs_currencies=usd",
        timeout=10
    )
    response.raise_for_status()
    hive_usd = response.json()["hive"]["usd"]
    reference_price = hive_usd
    print(f"CoinGecko HIVE price : {hive_usd:.6f} USD  (HBD ≈ 1 USD)")
except Exception as e:
    print(f"Error fetching CoinGecko: {e}")
    print("Falling back to internal lowest ask as reference.")
    ticker = market.ticker()
    reference_price = float(ticker['lowest_ask'])

# 4. Quick internal market snapshot
ticker = market.ticker()
lowest_ask = float(ticker['lowest_ask'])
highest_bid = float(ticker['highest_bid'])
premium = ((lowest_ask / reference_price) - 1) * 100
print(f"Internal lowest ask  : {lowest_ask:.6f} HBD/HIVE  ({premium:+.3f}% vs CoinGecko)")
print(f"Internal highest bid : {highest_bid:.6f} HBD/HIVE")

# 5. Fetch orderbook (we only care about asks = people selling HIVE)
orderbook = market.orderbook(limit=orderbook_limit, raw_data=True)
asks = orderbook.get('asks', [])

if not asks:
    print("\nNo asks found on the internal market.")
    exit()

# ----------------------------------------------------
# 6. Show top 20 asks with cumulative HBD + mark slippage point
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

# If we never hit the limit inside the top 20, keep going deeper
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
# 7. Final summary (HBD → HIVE)
# ----------------------------------------------------
print("\n" + "=" * 78)
print("RESULT (HBD → HIVE on Hive internal market)")
print("=" * 78)

if max_hbd_within_tolerance > 0:
    avg_price = max_hbd_within_tolerance / max_hive_within_tolerance
    actual_slip = ((avg_price / reference_price) - 1) * 100

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

# ----------------------------------------------------
# 8. Hypothetical: sell the received HIVE on Upbit for KRW
# ----------------------------------------------------
if max_hive_within_tolerance > 0:
    print("\n" + "=" * 78)
    print("HYPOTHETICAL: Sell received HIVE on Upbit (KRW-HIVE bids)")
    print("=" * 78)

    try:
        upbit_resp = requests.get(
            "https://api.upbit.com/v1/orderbook",
            params={
                "markets": "KRW-HIVE",
                "count": upbit_orderbook_count,
            },
            timeout=10,
        )
        upbit_resp.raise_for_status()
        upbit_data = upbit_resp.json()

        if not upbit_data or not isinstance(upbit_data, list):
            raise ValueError("Unexpected Upbit response format")

        units = upbit_data[0].get("orderbook_units", [])
        if not units:
            print("No orderbook units returned from Upbit.")
        else:
            # Show top 10 bid levels for transparency
            print(f"\nUpbit KRW-HIVE top bid levels (best first):")
            print(f"{'#':>3}  {'Bid Price':>12}  {'Bid Size (HIVE)':>16}  {'Cumul HIVE':>12}  {'Cumul KRW':>14}")
            print("-" * 70)

            preview_cum_hive = 0.0
            preview_cum_krw = 0.0
            for i, u in enumerate(units[:10], 1):
                bp = float(u["bid_price"])
                bs = float(u["bid_size"])
                preview_cum_hive += bs
                preview_cum_krw += bp * bs
                print(f"{i:>3}  {bp:12.1f}  {bs:16.4f}  {preview_cum_hive:12.3f}  {preview_cum_krw:14,.0f}")

            # Now simulate selling the exact amount of HIVE we received
            remaining_hive = max_hive_within_tolerance
            krw_received = 0.0
            levels_used = 0

            for u in units:
                bid_price = float(u["bid_price"])
                bid_size = float(u["bid_size"])

                if remaining_hive <= 0:
                    break

                take = min(remaining_hive, bid_size)
                krw_received += take * bid_price
                remaining_hive -= take
                levels_used += 1

            hive_sold = max_hive_within_tolerance - remaining_hive

            print("\n" + "-" * 70)
            print("Fill simulation against Upbit bids:")
            print(f"  HIVE to sell          : {max_hive_within_tolerance:,.3f}")
            print(f"  HIVE actually filled  : {hive_sold:,.3f}")
            print(f"  Levels consumed       : {levels_used}")

            if remaining_hive > 1e-6:  # floating point tolerance
                print(f"  WARNING: Unfilled     : {remaining_hive:,.3f} HIVE (insufficient depth in top {upbit_orderbook_count} levels)")
                print(f"  KRW received (partial): {krw_received:,.0f} KRW")
            else:
                avg_krw_per_hive = krw_received / hive_sold if hive_sold > 0 else 0.0
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
