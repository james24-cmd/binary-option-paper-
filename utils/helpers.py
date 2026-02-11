"""
Binary Options Trading Bot — Utilities
Logging setup, formatting helpers, and console output.
"""

import logging
import sys
from datetime import datetime


def setup_logging(level=logging.INFO):
    """Configure logging for the trading bot."""
    formatter = logging.Formatter(
        "%(asctime)s | %(name)-18s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger("bot")
    root.setLevel(level)

    if not root.handlers:
        root.addHandler(handler)

    return root


def format_currency(value: float) -> str:
    """Format a value as currency."""
    if value >= 0:
        return f"${value:.2f}"
    return f"-${abs(value):.2f}"


def format_pnl(value: float) -> str:
    """Format P&L with color indicator."""
    if value > 0:
        return f"+${value:.2f} 🟢"
    elif value < 0:
        return f"-${abs(value):.2f} 🔴"
    return "$0.00 ⚪"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a percentage value."""
    return f"{value:.{decimals}f}%"


def get_session_id() -> str:
    """Generate a unique session identifier."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")
