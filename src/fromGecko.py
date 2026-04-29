# main.py
from beem import Hive
from beem.nodelist import NodeList
from beem.market import Market
import sys
import requests

# ------------------- CONFIGURATION -------------------
orderbook_limit = 100  # How many orders to fetch (increase if you expect deep fills)
top_orders_to_show = 20
# ----------------------------------------------------

# Ask user for direction
while True:
    action_input = input("Do you want to BUY or SELL HIVE? (buy/sell): ").strip().lower()
    if action_input in ['buy', 'sell']:
        action = action_input
        is_buy = action == 'buy'
        break
    print("Error: Please enter 'buy' or 'sell'.")

print(f"\nYou selected: {action.upper()} HIVE")

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

# Fetch Coingecko HIVE/USD price only (HBD assumed = 1 USD)
print("\n--- Fetching external reference price from Coingecko ---")
try:
    response = requests.get(
        "https://api.coingecko.com/api/v3/simple/price?ids=hive&vs_currencies=usd",
        timeout=10
    )
    response.raise_for_status()
    hive_usd = response.json()["hive"]["usd"]
    reference_price = hive_usd
    print(f"Coingecko HIVE/USD : {hive_usd:.6f} USD (HBD ≈ 1 USD)")
except Exception as e:
    print(f"Error fetching Coingecko price: {e}")
    print("Falling back to internal price as reference.")
    reference_price = internal_lowest_ask if is_buy else internal_highest_bid

print(f"\nReference price used for slippage: {reference_price:.6f} USD/HIVE (HBD ≈ 1)")

# Show premium/discount of internal market vs Coingecko
if is_buy:
    premium_ask_pct = ((internal_lowest_ask / reference_price) - 1) * 100
    print(f"Internal lowest ask premium vs Coingecko: {premium_ask_pct:+.4f}%")
else:
    premium_bid_pct = ((internal_highest_bid / reference_price) - 1) * 100
    print(f"Internal highest bid vs Coingecko: {premium_bid_pct:+.4f}%")

# Get order book
orderbook = market.orderbook(limit=orderbook_limit, raw_data=True)

# Show top orders for context (opposite side)
print(f"\n--- Top {top_orders_to_show} {'Bids' if is_buy else 'Asks'} (for context) ---")
side_to_show = orderbook['bids'] if is_buy else orderbook['asks']
for order in side_to_show[:top_orders_to_show]:
    price = float(order['real_price'])
    hive_amount = order['hive'] / 1000.0
    hbd_amount = order['hbd'] / 1000.0
    print(f"{hive_amount:8.3f} HIVE @ {price:.6f} HBD ({'pay' if is_buy else 'receive'} {hbd_amount:8.3f} HBD)")

# Select side to fill
if is_buy:
    orders = orderbook['asks']
    sim_title = f"BUYING HIVE by filling asks until slippage > {tolerable_slip_pct}%"
    stop_condition = lambda s: s > tolerable_slip_pct
else:
    orders = orderbook['bids']
    sim_title = f"SELLING HIVE by filling bids until slippage < -{tolerable_slip_pct}%"
    stop_condition = lambda s: s < -tolerable_slip_pct

print(f"\n--- Slippage Simulation: {sim_title} vs Coingecko ({reference_price:.6f}) ---")

cumulative_hive = 0.0
cumulative_hbd = 0.0
orders_used = 0

for i, order in enumerate(orders):
    hive_amount = order['hive'] / 1000.0
    hbd_amount = order['hbd'] / 1000.0
    price = float(order['real_price'])
    
    # Temporary values if we add this order
    temp_hive = cumulative_hive + hive_amount
    temp_hbd = cumulative_hbd + hbd_amount
    temp_avg = temp_hbd / temp_hive if temp_hive > 0 else price
    temp_slippage_pct = ((temp_avg / reference_price) - 1) * 100
   
    if stop_condition(temp_slippage_pct):
        direction_msg = f"exceeds {tolerable_slip_pct}%" if is_buy else f"exceeds -{tolerable_slip_pct}%"
        print(f"\nStopped before order {i+1}: adding it would cause {temp_slippage_pct:+.4f}% slippage ({direction_msg})")
        break
   
    # Accept the order
    cumulative_hive = temp_hive
    cumulative_hbd = temp_hbd
    orders_used = i + 1
    verb = "for" if is_buy else "receiving"
    print(f"Order {i+1:3d}: +{hive_amount:8.3f} HIVE {verb} {hbd_amount:8.3f} HBD @ {price:.6f} → cumul slip: {temp_slippage_pct:+.4f}%")
else:
    print("\nReached end of fetched orders without exceeding slippage tolerance.")

# Show the orders used
print(f"\n--- Top {orders_used} {'Asks' if is_buy else 'Bids'} Used in Simulation ---")
cumulative_hbd_liquidity = 0.0
for i in range(orders_used):
    order = orders[i]
    price = float(order['real_price'])
    hive_amount = order['hive'] / 1000.0
    hbd_amount = order['hbd'] / 1000.0
    cumulative_hbd_liquidity += hbd_amount
    direction = "pay" if is_buy else "receive"
    print(f"{i+1:2d}: {hive_amount:8.3f} HIVE @ {price:.6f} HBD → {direction} {hbd_amount:8.3f} HBD")

liquidity_desc = f"HBD needed to buy" if is_buy else f"HBD receivable by selling"
print(f"\n>>> Total liquidity within {tolerable_slip_pct}% slippage vs Coingecko: {cumulative_hbd_liquidity:.3f} HBD (≈USD) {liquidity_desc} {cumulative_hive:.3f} HIVE <<<")

# Final results
if cumulative_hive > 0:
    avg_price = cumulative_hbd / cumulative_hive
    slippage_pct = ((avg_price / reference_price) - 1) * 100
    print(f"\n=== Results ({action.upper()}ING HIVE, staying within {tolerable_slip_pct}% slippage vs Coingecko) ===")
    print(f"Orders used           : {orders_used}")
    print(f"Total HIVE {'received' if is_buy else 'sold'}     : {cumulative_hive:.3f} HIVE")
    print(f"Total HBD {'spent' if is_buy else 'received'}       : {cumulative_hbd:.3f} HBD")
    print(f"Average price paid/received : {avg_price:.6f} HBD per HIVE")
    print(f"Coingecko reference   : {reference_price:.6f} USD per HIVE")
    print(f"Actual slippage       : {slippage_pct:+.4f}%")
    if is_buy:
        print(f"HIVE per HBD          : {cumulative_hive / cumulative_hbd:.4f} (higher = better)")
    else:
        print(f"HBD per HIVE          : {cumulative_hbd / cumulative_hive:.4f} (higher = better)")
else:
    print("\nNo liquidity available within the slippage tolerance (internal prices too far from Coingecko).")
