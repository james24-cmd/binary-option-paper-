"""
Binary Options Trading Bot — Market Data Feed
Fetches OHLCV data via yfinance for multiple symbols and timeframes.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger("bot.data_feed")


class DataFeed:
    """Fetches and caches market data from Yahoo Finance."""

    def __init__(self):
        self._cache = {}
        self._cache_expiry = {}
        self._cache_ttl = 15  # seconds

    def get_data(self, symbol: str, yf_ticker: str, timeframe: str = "5m",
                 bars: int = 200) -> pd.DataFrame | None:
        """
        Fetch OHLCV data for a symbol.

        Args:
            symbol: Display name (e.g. "EUR/USD")
            yf_ticker: Yahoo Finance ticker (e.g. "EURUSD=X")
            timeframe: Candle timeframe ("1m", "5m", "15m")
            bars: Number of bars to fetch

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
            None if fetch fails
        """
        cache_key = f"{yf_ticker}_{timeframe}"
        now = time.time()

        # Return cached data if still fresh
        if cache_key in self._cache and now < self._cache_expiry.get(cache_key, 0):
            logger.debug(f"Cache hit for {symbol} [{timeframe}]")
            return self._cache[cache_key]

        try:
            # Determine period based on timeframe
            period_map = {
                "1m": "1d",
                "5m": "5d",
                "15m": "5d",
            }
            period = period_map.get(timeframe, "5d")

            ticker = yf.Ticker(yf_ticker)
            df = ticker.history(period=period, interval=timeframe)

            if df is None or df.empty:
                logger.warning(f"No data for {symbol} [{timeframe}]")
                return None

            # Standardize columns
            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            })

            # Keep only what we need
            cols = ["open", "high", "low", "close", "volume"]
            available = [c for c in cols if c in df.columns]
            df = df[available].tail(bars)

            # Cache it
            self._cache[cache_key] = df
            self._cache_expiry[cache_key] = now + self._cache_ttl
            logger.info(f"Fetched {len(df)} bars for {symbol} [{timeframe}]")
            return df

        except Exception as e:
            logger.error(f"Data fetch error for {symbol}: {e}")
            return None

    def get_current_price(self, yf_ticker: str) -> float | None:
        """Get the latest price for a ticker."""
        try:
            ticker = yf.Ticker(yf_ticker)
            data = ticker.history(period="1d", interval="1m")
            if data is not None and not data.empty:
                return float(data["Close"].iloc[-1])
        except Exception as e:
            logger.error(f"Price fetch error for {yf_ticker}: {e}")
        return None

    def get_multi_timeframe_data(self, symbol: str, yf_ticker: str,
                                  timeframes: list[str]) -> dict[str, pd.DataFrame]:
        """Fetch data for multiple timeframes."""
        result = {}
        for tf in timeframes:
            df = self.get_data(symbol, yf_ticker, tf)
            if df is not None:
                result[tf] = df
        return result

    def clear_cache(self):
        """Clear the data cache."""
        self._cache.clear()
        self._cache_expiry.clear()
