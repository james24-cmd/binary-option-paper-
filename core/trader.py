"""
Binary Options Trading Bot — Trade Execution Engine
Manages the full trade lifecycle: signal → risk check → execute → resolve.
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import random

import config
from core.signals import Signal
from core.risk_manager import RiskManager

logger = logging.getLogger("bot.trader")


@dataclass
class Trade:
    """Represents an active binary options trade."""
    id: int
    symbol: str
    direction: str  # "CALL" or "PUT"
    entry_price: float
    stake: float
    confidence: float
    entry_time: datetime = field(default_factory=datetime.now)
    expiry_time: datetime = None
    exit_price: float = None
    result: str = None  # "WIN", "LOSS", or None
    pnl: float = 0.0
    resolved: bool = False

    def __post_init__(self):
        if self.expiry_time is None:
            self.expiry_time = self.entry_time + timedelta(
                minutes=config.TRADE_EXPIRY_MINUTES
            )

    @property
    def time_remaining(self) -> timedelta:
        return max(timedelta(0), self.expiry_time - datetime.now())

    @property
    def is_expired(self) -> bool:
        return datetime.now() >= self.expiry_time

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stake": f"${self.stake:.2f}",
            "confidence": f"{self.confidence:.1f}%",
            "entry_time": self.entry_time.strftime("%H:%M:%S"),
            "expiry_time": self.expiry_time.strftime("%H:%M:%S"),
            "time_remaining": str(self.time_remaining).split(".")[0],
            "result": self.result or "ACTIVE",
            "pnl": f"${self.pnl:+.2f}" if self.resolved else "—",
        }


class TradingEngine:
    """
    Manages binary options trading.

    Flow: Signal → Risk Check → Position Size → Execute → Wait → Resolve
    """

    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager
        self.active_trades: list[Trade] = []
        self.completed_trades: list[Trade] = []
        self._trade_counter = 0
        self._signal_log: list[dict] = []

    def process_signal(self, signal: Signal) -> Trade | None:
        """
        Process a trading signal through the full pipeline.

        Steps:
        1. Check risk management approval
        2. Calculate position size
        3. Execute the trade (paper)

        Returns Trade if executed, None if blocked.
        """
        # Log the signal regardless
        self._signal_log.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "symbol": signal.symbol,
            "direction": signal.direction,
            "confidence": signal.confidence,
            "price": signal.price,
            "action": "PENDING",
        })

        # Check risk management
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            self._signal_log[-1]["action"] = f"BLOCKED: {reason}"
            logger.info(f"Trade blocked for {signal.symbol}: {reason}")
            return None

        # Calculate position size
        stake = self.risk_manager.calculate_position_size()

        # Execute trade
        self._trade_counter += 1
        trade = Trade(
            id=self._trade_counter,
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=signal.price,
            stake=stake,
            confidence=signal.confidence,
        )

        self.active_trades.append(trade)
        self.risk_manager.open_trade()
        self._signal_log[-1]["action"] = f"EXECUTED (${stake:.2f})"

        logger.info(
            f"Trade #{trade.id} OPENED: {trade.direction} {trade.symbol} "
            f"@ {trade.entry_price} | Stake: ${trade.stake:.2f} | "
            f"Confidence: {trade.confidence:.1f}%"
        )

        return trade

    def check_and_resolve_trades(self, current_prices: dict[str, float]):
        """
        Check all active trades and resolve expired ones.

        Args:
            current_prices: Dict mapping symbol display names to current prices
        """
        still_active = []

        for trade in self.active_trades:
            if trade.is_expired:
                # Get exit price
                exit_price = current_prices.get(trade.symbol)
                if exit_price is None:
                    # If we can't get a price, extend expiry by 1 minute
                    trade.expiry_time += timedelta(minutes=1)
                    still_active.append(trade)
                    continue

                trade.exit_price = exit_price
                self._resolve_trade(trade)
                self.completed_trades.append(trade)
                self.risk_manager.close_trade()
            else:
                still_active.append(trade)

        self.active_trades = still_active

    def _resolve_trade(self, trade: Trade):
        """Determine if a trade won or lost based on price movement."""
        if trade.exit_price is None:
            return

        if trade.direction == "CALL":
            won = trade.exit_price > trade.entry_price
        else:  # PUT
            won = trade.exit_price < trade.entry_price

        trade.resolved = True

        if won:
            trade.result = "WIN"
            trade.pnl = trade.stake * config.PAYOUT_RATE
        else:
            trade.result = "LOSS"
            trade.pnl = -trade.stake

        # Record with risk manager
        self.risk_manager.record_trade_result(
            won=won,
            amount=trade.stake,
            trade_info={
                "symbol": trade.symbol,
                "direction": trade.direction,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "confidence": trade.confidence,
            }
        )

        logger.info(
            f"Trade #{trade.id} RESOLVED: {trade.result} | "
            f"{trade.direction} {trade.symbol} | "
            f"Entry: {trade.entry_price:.5f} → Exit: {trade.exit_price:.5f} | "
            f"P&L: ${trade.pnl:+.2f}"
        )

    def simulate_demo_losses(self, count: int = 3):
        """
        Simulate a series of losing trades for demo/testing purposes.
        Demonstrates risk management rules in action.
        """
        for i in range(count):
            can_trade, reason = self.risk_manager.can_trade()
            stake = self.risk_manager.calculate_position_size()

            self._trade_counter += 1
            trade = Trade(
                id=self._trade_counter,
                symbol="DEMO",
                direction="CALL",
                entry_price=1.0000,
                stake=stake,
                confidence=75.0,
                entry_time=datetime.now() - timedelta(minutes=config.TRADE_EXPIRY_MINUTES + 1),
            )
            trade.exit_price = 0.9990
            trade.resolved = True
            trade.result = "LOSS"
            trade.pnl = -stake

            if can_trade:
                self.risk_manager.record_trade_result(
                    won=False, amount=stake,
                    trade_info={
                        "symbol": "DEMO",
                        "direction": "CALL",
                        "entry_price": 1.0,
                        "exit_price": 0.999,
                        "confidence": 75.0,
                    }
                )
                self.completed_trades.append(trade)
                logger.info(f"Demo loss #{i+1}: -${stake:.2f}")
            else:
                logger.info(f"Demo trade #{i+1} BLOCKED: {reason}")
                break

    def get_signal_log(self) -> list[dict]:
        """Return the signal log for dashboard display."""
        return list(reversed(self._signal_log[-50:]))

    def get_active_trades_data(self) -> list[dict]:
        """Return active trades as dicts for dashboard."""
        return [t.to_dict() for t in self.active_trades]

    def get_completed_trades_data(self) -> list[dict]:
        """Return completed trades as dicts for dashboard."""
        return [t.to_dict() for t in reversed(self.completed_trades[-100:])]

    def get_stats(self) -> dict:
        """Get trading engine statistics."""
        total = len(self.completed_trades)
        wins = sum(1 for t in self.completed_trades if t.result == "WIN")
        losses = sum(1 for t in self.completed_trades if t.result == "LOSS")
        total_pnl = sum(t.pnl for t in self.completed_trades)

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total * 100) if total > 0 else 0,
            "total_pnl": total_pnl,
            "active_count": len(self.active_trades),
            "best_trade": max((t.pnl for t in self.completed_trades), default=0),
            "worst_trade": min((t.pnl for t in self.completed_trades), default=0),
        }
