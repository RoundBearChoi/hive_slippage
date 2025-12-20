from beem import Hive
from beem.nodelist import NodeList
from beem.market import Market

# ------------------- CONFIGURATION -------------------
tolerable_slip_pct = 0.5  # Stop when slippage would exceed this % vs best ask
orderbook_limit = 100     # How many orders to fetch (increase if you expect deep fills)
top_bids_to_show = 20
# ----------------------------------------------------

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
print(f"Latest price : {float(ticker['latest']):.6f} HBD per HIVE")
print(f"Highest bid : {float(ticker['highest_bid']):.6f} HBD per HIVE")
print(f"Lowest ask : {float(ticker['lowest_ask']):.6f} HBD per HIVE")

best_price = float(ticker['lowest_ask'])

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

# Slippage simulation: fill asks until tolerance is exceeded
print(f"\n--- Slippage Simulation: Filling asks until slippage > {tolerable_slip_pct}% vs best ask ({best_price:.6f}) ---")

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
    temp_slippage_pct = ((temp_avg / best_price) - 1) * 100

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

print(f"\n>>> Total liquidity within {tolerable_slip_pct}% slippage: {cumulative_hbd_liquidity:.3f} HBD worth of HIVE available <<<")

# Final results
if cumulative_hive > 0:
    avg_price = cumulative_cost / cumulative_hive
    slippage_pct = ((avg_price / best_price) - 1) * 100
    hive_per_hbd = cumulative_hive / cumulative_cost
    print(f"\n=== Results (staying within {tolerable_slip_pct}% slippage) ===")
    print(f"Orders used         : {orders_used}")
    print(f"Total HIVE you get  : {cumulative_hive:.3f} HIVE")
    print(f"Total HBD you spend : {cumulative_cost:.3f} HBD")
    print(f"Average price       : {avg_price:.6f} HBD per HIVE")
    print(f"Best ask price      : {best_price:.6f} HBD per HIVE")
    print(f"Actual slippage     : {slippage_pct:+.4f}%")
    print(f"HIVE per HBD        : {hive_per_hbd:.4f} (higher = better)")
else:
    print("\nNo liquidity available within the slippage tolerance.")
