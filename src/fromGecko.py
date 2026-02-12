# main.py
from beem import Hive
from beem.nodelist import NodeList
from beem.market import Market
import sys
import requests

# ------------------- CONFIGURATION -------------------
orderbook_limit = 100  # How many orders to fetch (increase if you expect deep fills)
top_bids_to_show = 20
# ----------------------------------------------------

# Ask user for tolerable slippage
while True:
    user_input = input("What's the tolerable slippage %? ").strip()
   
    if not user_input:
        print("Error: No input provided.")
        continue
   
    # Remove % sign if present
    if user_input.endswith('%'):
        user_input = user_input[:-1]
   
    try:
        tolerable_slip_pct = float(user_input)
        if tolerable_slip_pct < 0:
            print("Error: Slippage tolerance cannot be negative.")
            continue
        break
    except ValueError:
        print("Error: Invalid input. Please enter a valid number")
        continue

print(f"Using tolerable slippage: {tolerable_slip_pct}%")

# Connect to Hive nodes
nodelist = NodeList()
nodelist.update_nodes()
hive_nodes = nodelist.get_hive_nodes()
hive = Hive(node=hive_nodes)
print("Connected to Hive blockchain!")
print("Current block:", hive.get_dynamic_global_properties()['head_block_number'])

# Internal market: base=HIVE, quote=HBD
market = Market(base="HIVE", quote="HBD", blockchain_instance=hive)

# Ticker
ticker = market.ticker()
print("\n--- Internal Market Ticker ---")
internal_latest = float(ticker['latest'])
internal_highest_bid = float(ticker['highest_bid'])
internal_lowest_ask = float(ticker['lowest_ask'])
print(f"Latest price : {internal_latest:.6f} HBD per HIVE")
print(f"Highest bid  : {internal_highest_bid:.6f} HBD per HIVE")
print(f"Lowest ask   : {internal_lowest_ask:.6f} HBD per HIVE")

# Fetch Coingecko HIVE/USD price (reference price)
print("\n--- Fetching external reference price from Coingecko ---")
try:
    response = requests.get(
        "https://api.coingecko.com/api/v3/simple/price?ids=hive&vs_currencies=usd",
        timeout=10
    )
    response.raise_for_status()
    coingecko_price_usd = response.json()["hive"]["usd"]
    print(f"Coingecko HIVE/USD : {coingecko_price_usd:.6f} USD")
except Exception as e:
    print(f"Error fetching Coingecko price: {e}")
    print("Falling back to internal lowest ask as reference.")
    coingecko_price_usd = internal_lowest_ask

reference_price = coingecko_price_usd
print(f"\nReference price used for slippage: {reference_price:.6f} USD/HIVE (assuming HBD ≈ 1 USD)")

# Show premium/discount of internal market vs Coingecko
premium_ask_pct = ((internal_lowest_ask / reference_price) - 1) * 100
premium_latest_pct = ((internal_latest / reference_price) - 1) * 100
print(f"Internal lowest ask premium vs Coingecko: {premium_ask_pct:+.4f}%")
print(f"Internal latest price premium vs Coingecko: {premium_latest_pct:+.4f}%")

# Get order book
orderbook = market.orderbook(limit=orderbook_limit, raw_data=True)
asks = orderbook['asks']

# Show top bids (for context)
print(f"\n--- Top {top_bids_to_show} Bids (People wanting to buy HIVE with HBD) ---")
for bid in orderbook['bids'][:top_bids_to_show]:
    price = float(bid['real_price'])
    hive_receive = bid['hive'] / 1000.0
    hbd_pay = bid['hbd'] / 1000.0
    print(f"{hive_receive:8.3f} HIVE @ {price:.6f} HBD (pay {hbd_pay:8.3f} HBD)")

# Slippage simulation: fill asks until tolerance is exceeded vs Coingecko reference
print(f"\n--- Slippage Simulation: Buying HIVE by filling asks until slippage > {tolerable_slip_pct}% vs Coingecko ({reference_price:.6f}) ---")
cumulative_hive = 0.0
cumulative_cost = 0.0  # HBD spent
orders_used = 0

for i, ask in enumerate(asks):
    ask_hive = ask['hive'] / 1000.0
    ask_hbd = ask['hbd'] / 1000.0
    price = float(ask['real_price'])
    
    # Temporary values if we add this order
    temp_hive = cumulative_hive + ask_hive
    temp_cost = cumulative_cost + ask_hbd
    temp_avg = temp_cost / temp_hive if temp_hive > 0 else price
    temp_slippage_pct = ((temp_avg / reference_price) - 1) * 100
   
    if temp_slippage_pct > tolerable_slip_pct:
        print(f"\nStopped before order {i+1}: adding it would cause {temp_slippage_pct:+.4f}% slippage (exceeds {tolerable_slip_pct}%)")
        break
   
    # Accept the order
    cumulative_hive = temp_hive
    cumulative_cost = temp_cost
    orders_used = i + 1
    print(f"Order {i+1:3d}: +{ask_hive:8.3f} HIVE for {ask_hbd:8.3f} HBD @ {price:.6f} → cumul slip: {temp_slippage_pct:+.4f}%")
else:
    print("\nReached end of fetched orders without exceeding slippage tolerance.")

# Show the asks used
cumulative_hbd_liquidity = 0.0
print(f"\n--- Top {orders_used} Asks Used in Simulation ---")
for i in range(orders_used):
    ask = asks[i]
    price = float(ask['real_price'])
    hive_sell = ask['hive'] / 1000.0
    hbd_receive = ask['hbd'] / 1000.0
    cumulative_hbd_liquidity += hbd_receive
    print(f"{i+1:2d}: {hive_sell:8.3f} HIVE @ {price:.6f} HBD → {hbd_receive:8.3f} HBD (cumul: {cumulative_hbd_liquidity:8.3f} HBD)")

print(f"\n>>> Total liquidity within {tolerable_slip_pct}% slippage vs Coingecko: {cumulative_hbd_liquidity:.3f} HBD (≈USD) needed to buy {cumulative_hive:.3f} HIVE <<<")

# Final results
if cumulative_hive > 0:
    avg_price = cumulative_cost / cumulative_hive
    slippage_pct = ((avg_price / reference_price) - 1) * 100
    hive_per_hbd = cumulative_hive / cumulative_cost
    print(f"\n=== Results (staying within {tolerable_slip_pct}% slippage vs Coingecko) ===")
    print(f"Orders used           : {orders_used}")
    print(f"Total HIVE received   : {cumulative_hive:.3f} HIVE")
    print(f"Total HBD spent       : {cumulative_cost:.3f} HBD")
    print(f"Average price paid    : {avg_price:.6f} HBD per HIVE (≈USD)")
    print(f"Coingecko reference   : {reference_price:.6f} USD per HIVE")
    print(f"Actual slippage       : {slippage_pct:+.4f}%")
    print(f"HIVE per HBD          : {hive_per_hbd:.4f} (higher = better)")
else:
    print("\nNo liquidity available within the slippage tolerance (internal prices too high vs Coingecko).")
