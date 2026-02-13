import requests
from datetime import datetime, timezone

# Discover available HIVE trading pairs on Binance
exchange_info_url = "https://api.binance.com/api/v3/exchangeInfo"
response_info = requests.get(exchange_info_url)

if response_info.status_code != 200:
    print("Failed to fetch exchange info from Binance.")
else:
    symbols_data = response_info.json()["symbols"]
    hive_pairs = [s["symbol"] for s in symbols_data if "HIVE" in s["symbol"] and s["status"] == "TRADING"]
    
    if not hive_pairs:
        print("No active HIVE trading pairs found on Binance.")
    else:
        print("Available HIVE trading pairs on Binance:", hive_pairs)
        
        # Prefer HIVEUSDT (highest liquidity usually), fallback to first available
        symbol = "HIVEUSDT" if "HIVEUSDT" in hive_pairs else hive_pairs[0]
        print(f"\nUsing pair: {symbol}\n")

        # Get daily klines - limit=6 gives the last 5 completed days + current ongoing day
        klines_url = "https://api.binance.com/api/v3/klines"
        params_klines = {"symbol": symbol, "interval": "1d", "limit": 6}
        response_klines = requests.get(klines_url, params=params_klines)

        if response_klines.status_code == 200:
            klines = response_klines.json()

            if len(klines) < 6:
                print("Warning: Fewer than 6 days of data available (exchange may be new or low activity).\n")
            
            # Table for last completed days
            print("Last 5 completed UTC days (most recent first):\n")
            print(f"{'Date (UTC)':<12} {'Total (HIVE)':>18} {'Buy (HIVE)':>18} {'Sell (HIVE)':>18} {'Total (USDT)':>18} {'Buy (USDT)':>18} {'Sell (USDT)':>18}")
            print("-" * 132)
            
            completed_klines = klines[:-1]  # Exclude current partial day
            # Take only the last 5 completed if more are returned (safety)
            completed_klines = completed_klines[-5:]
            
            for kline in reversed(completed_klines):
                day_str = datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
                
                total_hive = float(kline[5])
                total_usdt = float(kline[7])
                buy_hive = float(kline[9])
                buy_usdt = float(kline[10])
                sell_hive = total_hive - buy_hive
                sell_usdt = total_usdt - buy_usdt
                
                print(f"{day_str:<12} {total_hive:>18,.2f} {buy_hive:>18,.2f} {sell_hive:>18,.2f} {total_usdt:>18,.2f} {buy_usdt:>18,.2f} {sell_usdt:>18,.2f}")
            
            print("\n")

            # Current ongoing UTC day (partial)
            if len(klines) >= 1:
                current = klines[-1]
                current_day = datetime.fromtimestamp(current[0] / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
                current_total_hive = float(current[5])
                current_total_usdt = float(current[7])
                current_buy_hive = float(current[9])
                current_buy_usdt = float(current[10])
                current_sell_hive = current_total_hive - current_buy_hive
                current_sell_usdt = current_total_usdt - current_buy_usdt
                
                print(f"Current ongoing UTC day (partial - {current_day}):")
                print(f"  Total volume: {current_total_hive:,.2f} HIVE / ${current_total_usdt:,.2f} USDT")
                print(f"  Buy volume (taker buys): {current_buy_hive:,.2f} HIVE / ${current_buy_usdt:,.2f} USDT")
                print(f"  Sell volume (taker sells): {current_sell_hive:,.2f} HIVE / ${current_sell_usdt:,.2f} USDT\n")

            # Rolling 24-hour volume
            ticker_url = "https://api.binance.com/api/v3/ticker/24hr"
            params_ticker = {"symbol": symbol}
            response_ticker = requests.get(ticker_url, params=params_ticker)

            if response_ticker.status_code == 200:
                ticker = response_ticker.json()
                vol_24h_hive = float(ticker["volume"])
                vol_24h_usdt = float(ticker["quoteVolume"])
                
                print("24-hour rolling volume (total only):")
                print(f"  {vol_24h_hive:,.2f} HIVE / ${vol_24h_usdt:,.2f} USDT")
                
                print("\nNotes:")
                print("- Buy/sell split uses taker volumes (aggressive/market buys vs sells) from daily klines.")
                print("- Binance public API does not provide buy/sell split for the rolling 24h period.")
                print("- USDT values are in Tether (stablecoin pegged 1:1 to USD, so ≈ USD value).")

        else:
            print("Failed to fetch klines data.")
