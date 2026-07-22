# coingecko_hive_price.py
# Dedicated module for fetching HIVE price from CoinGecko
# Single source of truth used by hive_orderbook.py (and any future scripts)
# that need a consistent HIVE/USD reference price.

import requests


def get_hive_usd_price(timeout: float = 10) -> float:
    """
    Fetch the current HIVE price in USD from CoinGecko's simple/price endpoint.

    Args:
        timeout: Request timeout in seconds.

    Returns:
        float: HIVE/USD price.

    Raises:
        requests.RequestException: On network / HTTP errors.
        ValueError: If the response JSON shape is unexpected.
    """
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "hive",
        "vs_currencies": "usd",
    }

    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    try:
        return float(data["hive"]["usd"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Unexpected CoinGecko response format: {data}") from e
