from beem import Hive
from beem.nodelist import NodeList
from beem.market import Market

# ------------------- CONFIGURATION -------------------
top_x = 20
amount_hbd = 100000.0
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
print(f"Highest bid  : {float(ticker['highest_bid']):.6f} HBD per HIVE")
print(f"Lowest ask   : {float(ticker['lowest_ask']):.6f} HBD per HIVE")

# Get order book
orderbook = market.orderbook(limit=top_x, raw_data=True)

# Show top bids (buy side)
print(f"\n--- Top {top_x} Bids (People wanting to buy HIVE with HBD) ---")
for bid in orderbook['bids'][:top_x]:
    price = float(bid['real_price'])
    hive_receive = bid['hive'] / 1000.0
    hbd_pay = bid['hbd'] / 1000.0
    print(f"{hive_receive:8.3f} HIVE @ {price:.6f} HBD  (pay {hbd_pay:8.3f} HBD)")

# Show top asks with cumulative liquidity
print(f"\n--- Top {top_x} Asks (People selling HIVE for HBD) ---")
cumulative_hbd = 0.0
for i, ask in enumerate(orderbook['asks'][:top_x]):
    price = float(ask['real_price'])
    hive_sell = ask['hive'] / 1000.0
    hbd_receive = ask['hbd'] / 1000.0
    cumulative_hbd += hbd_receive
    print(f"{i+1:2d}: {hive_sell:8.3f} HIVE @ {price:.6f} HBD → {hbd_receive:8.3f} HBD  (cumul: {cumulative_hbd:8.3f} HBD)")

print(f"\n>>> Total liquidity in top {top_x} asks: {cumulative_hbd:.3f} HBD worth of HIVE available <<<")

# Slippage simulation
cumulative_hive = 0.0
cumulative_cost = 0.0
remaining_hbd = amount_hbd

print(f"\n--- Slippage Simulation: Market sell {amount_hbd:.1f} HBD (filling top {top_x} asks) ---")

for i, ask in enumerate(orderbook['asks'][:top_x]):
    ask_hive = ask['hive'] / 1000.0
    ask_hbd = ask['hbd'] / 1000.0
    price = float(ask['real_price'])

    if remaining_hbd >= ask_hbd:
        cumulative_hive += ask_hive
        cumulative_cost += ask_hbd
        remaining_hbd -= ask_hbd
        print(f"Order {i+1:2d}: +{ask_hive:8.3f} HIVE for {ask_hbd:8.3f} HBD @ {price:.6f}")
    else:
        partial_hive = remaining_hbd / price if price > 0 else 0
        cumulative_hive += partial_hive
        cumulative_cost += remaining_hbd
        print(f"Order {i+1:2d}: +{partial_hive:8.3f} HIVE for {remaining_hbd:8.3f} HBD @ {price:.6f} (partial)")
        remaining_hbd = 0
        break

filled = amount_hbd - remaining_hbd
if remaining_hbd > 0:
    print(f"\nWarning: Only filled {filled:.3f} HBD out of {amount_hbd:.1f} using top {top_x} asks.")
    print(f"Remaining {remaining_hbd:.3f} HBD would require going much deeper (likely very bad rates).")
else:
    print(f"\nSuccess: Full {amount_hbd:.1f} HBD filled within top {top_x} asks!")

# Final results
best_price = float(ticker['lowest_ask'])
if cumulative_hive > 0:
    avg_price = cumulative_cost / cumulative_hive
    slippage_pct = ((avg_price / best_price) - 1) * 100
    hive_per_hbd = cumulative_hive / cumulative_cost

    print(f"\n=== Results (for {filled:.3f} HBD filled) ===")
    print(f"Total HIVE received : {cumulative_hive:.3f} HIVE")
    print(f"Total HBD spent     : {cumulative_cost:.3f} HBD")
    print(f"Average price       : {avg_price:.6f} HBD per HIVE")
    print(f"Best ask price      : {best_price:.6f} HBD per HIVE")
    print(f"Estimated slippage  : {slippage_pct:+.2f}% vs best ask")
    print(f"HIVE per HBD        : {hive_per_hbd:.4f} (higher = better for you)")
else:
    print("No liquidity available.")
