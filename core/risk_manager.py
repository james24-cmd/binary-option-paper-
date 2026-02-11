"""
Binary Options Trading Bot — Strict Risk Management Engine
Enforces all risk rules BEFORE every trade is allowed to execute.
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import config

logger = logging.getLogger("bot.risk_manager")


@dataclass
class DailyStats:
    """Tracks daily trading statistics."""
    date: str = ""
    starting_balance: float = 0.0
    trades_taken: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    consecutive_losses: int = 0
    cooldown_until: datetime | None = None

    @property
    def win_rate(self) -> float:
        if self.trades_taken == 0:
            return 0.0
        return (self.wins / self.trades_taken) * 100

    @property
    def daily_loss_pct(self) -> float:
        if self.starting_balance == 0:
            return 0.0
        return abs(min(0, self.total_pnl)) / self.starting_balance * 100


class RiskManager:
    """
    Strict risk management engine.

    Rules enforced:
    1. Max risk per trade: 2% of current balance
    2. Max daily loss: 5% of starting daily balance
    3. Max consecutive losses: pause after 3
    4. Cooldown period: 10 min after loss streak
    5. Max open trades: 2 simultaneous
    6. Minimum balance: stop if < 10% of initial capital
    """

    def __init__(self, balance: float = None):
        self.initial_balance = balance or config.INITIAL_BALANCE
        self.balance = self.initial_balance
        self.daily_stats = DailyStats()
        self.open_trades_count = 0
        self.trade_history: list[dict] = []
        self._reset_daily_stats()

    def _reset_daily_stats(self):
        """Reset daily stats for a new trading day."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.daily_stats.date != today:
            self.daily_stats = DailyStats(
                date=today,
                starting_balance=self.balance,
            )
            logger.info(f"Daily stats reset. Balance: ${self.balance:.2f}")

    def can_trade(self) -> tuple[bool, str]:
        """
        Check ALL risk rules before allowing a trade.

        Returns:
            (allowed: bool, reason: str)
        """
        self._reset_daily_stats()

        # Rule 1: Minimum balance check
        min_balance = self.initial_balance * config.MIN_BALANCE_RATIO
        if self.balance < min_balance:
            reason = (f"🛑 BALANCE TOO LOW: ${self.balance:.2f} < "
                      f"${min_balance:.2f} minimum (10% of initial)")
            logger.warning(reason)
            return False, reason

        # Rule 2: Daily loss limit
        daily_loss_pct = self.daily_stats.daily_loss_pct
        max_daily_pct = config.MAX_DAILY_LOSS * 100
        if daily_loss_pct >= max_daily_pct:
            reason = (f"🛑 DAILY LOSS LIMIT: {daily_loss_pct:.1f}% lost today "
                      f"(max {max_daily_pct:.0f}%)")
            logger.warning(reason)
            return False, reason

        # Rule 3: Consecutive loss cooldown
        if self.daily_stats.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            if self.daily_stats.cooldown_until:
                if datetime.now() < self.daily_stats.cooldown_until:
                    remaining = (self.daily_stats.cooldown_until - datetime.now()).seconds // 60
                    reason = (f"⏸️ COOLDOWN ACTIVE: {remaining} min remaining "
                              f"after {config.MAX_CONSECUTIVE_LOSSES} consecutive losses")
                    logger.info(reason)
                    return False, reason
                else:
                    # Cooldown expired — reset streak
                    self.daily_stats.consecutive_losses = 0
                    self.daily_stats.cooldown_until = None
                    logger.info("Cooldown expired. Trading resumed.")

        # Rule 4: Max open trades
        if self.open_trades_count >= config.MAX_OPEN_TRADES:
            reason = (f"⏸️ MAX OPEN TRADES: {self.open_trades_count}/"
                      f"{config.MAX_OPEN_TRADES} positions open")
            logger.info(reason)
            return False, reason

        # Rule 5: Check if trade amount would be too small
        trade_amount = self.calculate_position_size()
        if trade_amount < 0.01:
            reason = f"🛑 POSITION TOO SMALL: ${trade_amount:.4f}"
            return False, reason

        return True, "✅ All risk checks passed"

    def calculate_position_size(self) -> float:
        """Calculate position size based on % risk of current balance."""
        size = self.balance * config.MAX_RISK_PER_TRADE
        # Round to 2 decimal places
        return round(size, 2)

    def record_trade_result(self, won: bool, amount: float, trade_info: dict = None):
        """
        Record a trade outcome and update all stats.

        Args:
            won: True if trade won
            amount: Trade stake amount
            trade_info: Additional trade metadata
        """
        self._reset_daily_stats()

        if won:
            profit = amount * config.PAYOUT_RATE
            self.balance += profit
            self.daily_stats.wins += 1
            self.daily_stats.total_pnl += profit
            self.daily_stats.consecutive_losses = 0
            logger.info(f"✅ WIN: +${profit:.2f} | Balance: ${self.balance:.2f}")
        else:
            self.balance -= amount
            self.daily_stats.losses += 1
            self.daily_stats.total_pnl -= amount
            self.daily_stats.consecutive_losses += 1
            logger.info(f"❌ LOSS: -${amount:.2f} | Balance: ${self.balance:.2f}")

            # Trigger cooldown if streak reached
            if self.daily_stats.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
                self.daily_stats.cooldown_until = (
                    datetime.now() + timedelta(minutes=config.COOLDOWN_MINUTES)
                )
                logger.warning(
                    f"🔴 COOLDOWN TRIGGERED: {config.MAX_CONSECUTIVE_LOSSES} "
                    f"consecutive losses. Pausing for {config.COOLDOWN_MINUTES} min."
                )

        self.daily_stats.trades_taken += 1

        # Store in history
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "result": "WIN" if won else "LOSS",
            "amount": amount,
            "pnl": amount * config.PAYOUT_RATE if won else -amount,
            "balance_after": self.balance,
            **(trade_info or {}),
        }
        self.trade_history.append(record)

    def open_trade(self):
        """Increment open trade counter."""
        self.open_trades_count += 1

    def close_trade(self):
        """Decrement open trade counter."""
        self.open_trades_count = max(0, self.open_trades_count - 1)

    def get_status(self) -> dict:
        """Get full risk management status for dashboard."""
        self._reset_daily_stats()
        trade_amount = self.calculate_position_size()
        can, reason = self.can_trade()

        return {
            "balance": self.balance,
            "initial_balance": self.initial_balance,
            "balance_change_pct": ((self.balance - self.initial_balance)
                                   / self.initial_balance * 100),
            "can_trade": can,
            "block_reason": reason,
            "trade_amount": trade_amount,
            "daily": {
                "trades": self.daily_stats.trades_taken,
                "wins": self.daily_stats.wins,
                "losses": self.daily_stats.losses,
                "win_rate": self.daily_stats.win_rate,
                "pnl": self.daily_stats.total_pnl,
                "loss_pct": self.daily_stats.daily_loss_pct,
                "max_daily_loss_pct": config.MAX_DAILY_LOSS * 100,
                "consecutive_losses": self.daily_stats.consecutive_losses,
                "max_consecutive": config.MAX_CONSECUTIVE_LOSSES,
            },
            "open_trades": self.open_trades_count,
            "max_open_trades": config.MAX_OPEN_TRADES,
            "cooldown_active": (
                self.daily_stats.cooldown_until is not None
                and datetime.now() < self.daily_stats.cooldown_until
            ),
            "cooldown_until": (
                self.daily_stats.cooldown_until.strftime("%H:%M:%S")
                if self.daily_stats.cooldown_until else None
            ),
            "min_balance": self.initial_balance * config.MIN_BALANCE_RATIO,
        }

    def get_equity_curve(self) -> list[dict]:
        """Return equity curve data from trade history."""
        curve = [{"trade": 0, "balance": self.initial_balance}]
        for i, trade in enumerate(self.trade_history):
            curve.append({
                "trade": i + 1,
                "balance": trade["balance_after"],
            })
        return curve
