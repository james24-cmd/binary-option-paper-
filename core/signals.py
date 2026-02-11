"""
Binary Options Trading Bot — Signal Analysis Engine
Generates CALL/PUT signals using multiple confluent technical indicators.
"""

import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands
import logging

import config

logger = logging.getLogger("bot.signals")


class Signal:
    """Represents a trading signal."""

    def __init__(self, symbol: str, direction: str, confidence: float,
                 indicators: dict, price: float, timeframe: str):
        self.symbol = symbol
        self.direction = direction  # "CALL" or "PUT"
        self.confidence = round(confidence, 1)  # 0-100
        self.indicators = indicators  # Individual indicator scores
        self.price = price
        self.timeframe = timeframe
        self.timestamp = pd.Timestamp.now()

    def __repr__(self):
        return (f"Signal({self.symbol} {self.direction} "
                f"conf={self.confidence}% @ {self.price})")

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "confidence": self.confidence,
            "price": self.price,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.strftime("%H:%M:%S"),
            "indicators": self.indicators,
        }


class SignalEngine:
    """
    Multi-indicator signal generator.
    Combines RSI, MACD, Bollinger Bands, EMA Cross, Stochastic,
    and Support/Resistance levels to produce a confidence score.
    """

    def __init__(self):
        self.weights = config.INDICATOR_WEIGHTS

    def analyze(self, symbol: str, df: pd.DataFrame,
                timeframe: str = "5m") -> Signal | None:
        """
        Analyze price data and generate a signal if confidence is sufficient.

        Returns Signal or None if no valid signal.
        """
        if df is None or len(df) < 50:
            return None

        try:
            scores = {}
            directions = {}

            # 1. RSI Analysis
            rsi_score, rsi_dir = self._analyze_rsi(df)
            scores["rsi"] = rsi_score
            directions["rsi"] = rsi_dir

            # 2. MACD Analysis
            macd_score, macd_dir = self._analyze_macd(df)
            scores["macd"] = macd_score
            directions["macd"] = macd_dir

            # 3. Bollinger Bands
            bb_score, bb_dir = self._analyze_bollinger(df)
            scores["bollinger"] = bb_score
            directions["bollinger"] = bb_dir

            # 4. EMA Cross
            ema_score, ema_dir = self._analyze_ema_cross(df)
            scores["ema_cross"] = ema_score
            directions["ema_cross"] = ema_dir

            # 5. Stochastic Oscillator
            stoch_score, stoch_dir = self._analyze_stochastic(df)
            scores["stochastic"] = stoch_score
            directions["stochastic"] = stoch_dir

            # 6. Support/Resistance
            sr_score, sr_dir = self._analyze_support_resistance(df)
            scores["support_resistance"] = sr_score
            directions["support_resistance"] = sr_dir

            # Determine overall direction by weighted vote
            call_weight = 0.0
            put_weight = 0.0
            for ind, direction in directions.items():
                w = self.weights.get(ind, 0) * scores.get(ind, 0)
                if direction == "CALL":
                    call_weight += w
                elif direction == "PUT":
                    put_weight += w

            if call_weight == 0 and put_weight == 0:
                return None

            if call_weight >= put_weight:
                overall_direction = "CALL"
                agreement_ratio = call_weight / (call_weight + put_weight) if (call_weight + put_weight) > 0 else 0
            else:
                overall_direction = "PUT"
                agreement_ratio = put_weight / (call_weight + put_weight) if (call_weight + put_weight) > 0 else 0

            # Calculate weighted confidence
            weighted_sum = sum(
                self.weights.get(ind, 0) * scores.get(ind, 0)
                for ind in scores
            )
            max_possible = sum(self.weights.values()) * 100
            confidence = (weighted_sum / max_possible) * 100 * agreement_ratio if max_possible > 0 else 0

            # Boost confidence if most indicators agree
            agreeing = sum(1 for d in directions.values() if d == overall_direction)
            if agreeing >= 5:
                confidence = min(100, confidence * 1.15)
            elif agreeing >= 4:
                confidence = min(100, confidence * 1.05)

            current_price = float(df["close"].iloc[-1])

            indicator_details = {
                ind: {"score": scores[ind], "direction": directions[ind]}
                for ind in scores
            }

            if confidence >= config.MIN_SIGNAL_CONFIDENCE:
                signal = Signal(
                    symbol=symbol,
                    direction=overall_direction,
                    confidence=confidence,
                    indicators=indicator_details,
                    price=current_price,
                    timeframe=timeframe,
                )
                logger.info(f"Signal generated: {signal}")
                return signal
            else:
                logger.debug(
                    f"{symbol}: confidence {confidence:.1f}% < "
                    f"{config.MIN_SIGNAL_CONFIDENCE}% threshold"
                )
                return None

        except Exception as e:
            logger.error(f"Signal analysis error for {symbol}: {e}")
            return None

    # ──────────────────────────────────────────
    #  INDIVIDUAL INDICATOR ANALYSIS
    # ──────────────────────────────────────────

    def _analyze_rsi(self, df: pd.DataFrame) -> tuple[float, str]:
        """RSI analysis. Returns (score 0-100, direction)."""
        try:
            rsi = RSIIndicator(df["close"], window=config.RSI_PERIOD)
            rsi_val = rsi.rsi().iloc[-1]

            if pd.isna(rsi_val):
                return 0, "NEUTRAL"

            if rsi_val <= config.RSI_OVERSOLD:
                strength = min(100, (config.RSI_OVERSOLD - rsi_val) / config.RSI_OVERSOLD * 200)
                return max(60, strength), "CALL"
            elif rsi_val >= config.RSI_OVERBOUGHT:
                strength = min(100, (rsi_val - config.RSI_OVERBOUGHT) / (100 - config.RSI_OVERBOUGHT) * 200)
                return max(60, strength), "PUT"
            else:
                # Mild bias based on which side of 50
                if rsi_val < 45:
                    return 30, "CALL"
                elif rsi_val > 55:
                    return 30, "PUT"
                return 0, "NEUTRAL"
        except Exception:
            return 0, "NEUTRAL"

    def _analyze_macd(self, df: pd.DataFrame) -> tuple[float, str]:
        """MACD analysis. Returns (score 0-100, direction)."""
        try:
            macd = MACD(df["close"], window_slow=config.MACD_SLOW,
                        window_fast=config.MACD_FAST,
                        window_sign=config.MACD_SIGNAL)
            macd_line = macd.macd().iloc[-1]
            signal_line = macd.macd_signal().iloc[-1]
            histogram = macd.macd_diff().iloc[-1]
            prev_histogram = macd.macd_diff().iloc[-2]

            if pd.isna(macd_line) or pd.isna(signal_line):
                return 0, "NEUTRAL"

            # Crossover detection
            if histogram > 0 and prev_histogram <= 0:
                return 85, "CALL"  # Bullish crossover
            elif histogram < 0 and prev_histogram >= 0:
                return 85, "PUT"   # Bearish crossover

            # Trend continuation
            if histogram > 0:
                if histogram > prev_histogram:
                    return 65, "CALL"  # Strengthening bullish
                return 45, "CALL"
            elif histogram < 0:
                if histogram < prev_histogram:
                    return 65, "PUT"   # Strengthening bearish
                return 45, "PUT"

            return 0, "NEUTRAL"
        except Exception:
            return 0, "NEUTRAL"

    def _analyze_bollinger(self, df: pd.DataFrame) -> tuple[float, str]:
        """Bollinger Bands analysis. Returns (score 0-100, direction)."""
        try:
            bb = BollingerBands(df["close"], window=config.BB_PERIOD,
                                window_dev=config.BB_STD_DEV)
            upper = bb.bollinger_hband().iloc[-1]
            lower = bb.bollinger_lband().iloc[-1]
            middle = bb.bollinger_mavg().iloc[-1]
            price = df["close"].iloc[-1]

            if pd.isna(upper) or pd.isna(lower):
                return 0, "NEUTRAL"

            band_width = upper - lower
            if band_width == 0:
                return 0, "NEUTRAL"

            position = (price - lower) / band_width  # 0 = at lower, 1 = at upper

            if position <= 0.05:  # At or below lower band
                return 80, "CALL"
            elif position >= 0.95:  # At or above upper band
                return 80, "PUT"
            elif position <= 0.2:
                return 55, "CALL"
            elif position >= 0.8:
                return 55, "PUT"
            elif position < 0.45:
                return 30, "CALL"
            elif position > 0.55:
                return 30, "PUT"
            return 0, "NEUTRAL"
        except Exception:
            return 0, "NEUTRAL"

    def _analyze_ema_cross(self, df: pd.DataFrame) -> tuple[float, str]:
        """EMA 9/21 crossover analysis. Returns (score 0-100, direction)."""
        try:
            ema_fast = EMAIndicator(df["close"], window=config.EMA_FAST).ema_indicator()
            ema_slow = EMAIndicator(df["close"], window=config.EMA_SLOW).ema_indicator()

            fast_now = ema_fast.iloc[-1]
            slow_now = ema_slow.iloc[-1]
            fast_prev = ema_fast.iloc[-2]
            slow_prev = ema_slow.iloc[-2]

            if pd.isna(fast_now) or pd.isna(slow_now):
                return 0, "NEUTRAL"

            # Fresh crossover
            if fast_prev <= slow_prev and fast_now > slow_now:
                return 90, "CALL"  # Bullish cross
            elif fast_prev >= slow_prev and fast_now < slow_now:
                return 90, "PUT"   # Bearish cross

            # Sustained trend
            gap_pct = abs(fast_now - slow_now) / slow_now * 100 if slow_now != 0 else 0
            if fast_now > slow_now:
                return min(70, 40 + gap_pct * 100), "CALL"
            elif fast_now < slow_now:
                return min(70, 40 + gap_pct * 100), "PUT"

            return 0, "NEUTRAL"
        except Exception:
            return 0, "NEUTRAL"

    def _analyze_stochastic(self, df: pd.DataFrame) -> tuple[float, str]:
        """Stochastic Oscillator analysis. Returns (score 0-100, direction)."""
        try:
            stoch = StochasticOscillator(
                df["high"], df["low"], df["close"],
                window=config.STOCH_K, smooth_window=config.STOCH_D
            )
            k_val = stoch.stoch().iloc[-1]
            d_val = stoch.stoch_signal().iloc[-1]

            if pd.isna(k_val) or pd.isna(d_val):
                return 0, "NEUTRAL"

            # Oversold with K crossing above D
            if k_val < config.STOCH_OVERSOLD:
                k_prev = stoch.stoch().iloc[-2]
                d_prev = stoch.stoch_signal().iloc[-2]
                if not pd.isna(k_prev) and not pd.isna(d_prev):
                    if k_prev <= d_prev and k_val > d_val:
                        return 85, "CALL"
                return 60, "CALL"

            # Overbought with K crossing below D
            elif k_val > config.STOCH_OVERBOUGHT:
                k_prev = stoch.stoch().iloc[-2]
                d_prev = stoch.stoch_signal().iloc[-2]
                if not pd.isna(k_prev) and not pd.isna(d_prev):
                    if k_prev >= d_prev and k_val < d_val:
                        return 85, "PUT"
                return 60, "PUT"

            # Mild signals
            if k_val < 40:
                return 25, "CALL"
            elif k_val > 60:
                return 25, "PUT"

            return 0, "NEUTRAL"
        except Exception:
            return 0, "NEUTRAL"

    def _analyze_support_resistance(self, df: pd.DataFrame) -> tuple[float, str]:
        """Support/Resistance level analysis. Returns (score 0-100, direction)."""
        try:
            lookback = min(config.SR_LOOKBACK, len(df))
            recent = df.tail(lookback)
            price = df["close"].iloc[-1]

            # Find pivot highs and lows
            highs = recent["high"].values
            lows = recent["low"].values

            resistance_levels = []
            support_levels = []

            for i in range(2, len(highs) - 2):
                # Pivot high (resistance)
                if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
                   highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                    resistance_levels.append(highs[i])
                # Pivot low (support)
                if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
                   lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                    support_levels.append(lows[i])

            if not support_levels and not resistance_levels:
                return 0, "NEUTRAL"

            tolerance = price * config.SR_TOLERANCE

            # Check proximity to support
            near_support = any(abs(price - s) <= tolerance for s in support_levels)
            # Check proximity to resistance
            near_resistance = any(abs(price - r) <= tolerance for r in resistance_levels)

            if near_support and not near_resistance:
                return 70, "CALL"  # Bouncing off support
            elif near_resistance and not near_support:
                return 70, "PUT"   # Rejected at resistance
            elif near_support and near_resistance:
                return 30, "NEUTRAL"  # Squeeze zone

            return 0, "NEUTRAL"
        except Exception:
            return 0, "NEUTRAL"
