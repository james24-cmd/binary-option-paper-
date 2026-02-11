"""
Binary Options Trading Bot — Streamlit Dashboard
Real-time monitoring of signals, trades, risk status, and performance.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core.data_feed import DataFeed
from core.signals import SignalEngine
from core.risk_manager import RiskManager
from core.trader import TradingEngine
from utils.helpers import setup_logging, format_currency, format_pnl

# ─────────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Binary Options Bot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load custom CSS
css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────
#  SESSION STATE INITIALIZATION
# ─────────────────────────────────────────────────
if "initialized" not in st.session_state:
    setup_logging()
    st.session_state.data_feed = DataFeed()
    st.session_state.signal_engine = SignalEngine()
    st.session_state.risk_manager = RiskManager(balance=config.INITIAL_BALANCE)
    st.session_state.trading_engine = TradingEngine(st.session_state.risk_manager)
    st.session_state.signals_history = []
    st.session_state.auto_trade = False
    st.session_state.last_scan = None
    st.session_state.initialized = True


def get_rm() -> RiskManager:
    return st.session_state.risk_manager


def get_te() -> TradingEngine:
    return st.session_state.trading_engine


def get_df() -> DataFeed:
    return st.session_state.data_feed


def get_se() -> SignalEngine:
    return st.session_state.signal_engine


# ─────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Binary Options Bot")
    st.markdown("---")

    status = get_rm().get_status()

    # Balance display
    balance_color = "#22c55e" if status["balance"] >= config.INITIAL_BALANCE else "#ef4444"
    st.markdown(
        f"<h2 style='text-align:center; color:{balance_color}; "
        f"font-family: monospace;'>"
        f"${status['balance']:.2f}</h2>",
        unsafe_allow_html=True,
    )

    change_pct = status["balance_change_pct"]
    change_icon = "📈" if change_pct >= 0 else "📉"
    st.markdown(
        f"<p style='text-align:center; color:#94a3b8; font-size:0.85rem;'>"
        f"{change_icon} {change_pct:+.1f}% from ${config.INITIAL_BALANCE:.2f}</p>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Risk Status
    st.markdown("### 🛡️ Risk Status")
    can_trade = status["can_trade"]
    if can_trade:
        st.success("✅ Trading Allowed")
    else:
        st.error(status["block_reason"])

    st.markdown(f"**Position Size:** ${status['trade_amount']:.2f}")
    st.markdown(f"**Open Trades:** {status['open_trades']}/{status['max_open_trades']}")

    # Daily stats
    daily = status["daily"]
    st.markdown(f"**Daily P&L:** {format_pnl(daily['pnl'])}")
    st.markdown(f"**Win Rate:** {daily['win_rate']:.0f}%")
    st.markdown(f"**Trades Today:** {daily['trades']}")
    st.markdown(
        f"**Loss Streak:** {daily['consecutive_losses']}/"
        f"{daily['max_consecutive']}"
    )

    # Daily loss bar
    loss_ratio = min(1.0, daily["loss_pct"] / daily["max_daily_loss_pct"]) if daily["max_daily_loss_pct"] > 0 else 0
    st.progress(loss_ratio, text=f"Daily Loss: {daily['loss_pct']:.1f}% / {daily['max_daily_loss_pct']:.0f}%")

    if status["cooldown_active"]:
        st.warning(f"⏸️ Cooldown until {status['cooldown_until']}")

    st.markdown("---")

    # Controls
    st.markdown("### ⚙️ Controls")
    auto_trade = st.toggle("🤖 Auto-Trade Mode", value=st.session_state.auto_trade)
    st.session_state.auto_trade = auto_trade

    col1, col2 = st.columns(2)
    with col1:
        scan_btn = st.button("🔍 Scan Now", use_container_width=True)
    with col2:
        demo_btn = st.button("🧪 Demo Loss", use_container_width=True)

    st.markdown("---")
    st.markdown(
        "<p style='text-align:center; color:#475569; font-size:0.7rem;'>"
        "⚠️ Paper Trading Only<br>Not Financial Advice</p>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────
#  HANDLE DEMO LOSSES
# ─────────────────────────────────────────────────
if demo_btn:
    get_te().simulate_demo_losses(count=1)
    st.rerun()


# ─────────────────────────────────────────────────
#  MARKET SCANNING
# ─────────────────────────────────────────────────
def scan_markets():
    """Scan all symbols for signals and optionally execute trades."""
    signals_found = []
    data_feed = get_df()
    signal_engine = get_se()
    trading_engine = get_te()

    # First resolve any expired trades
    current_prices = {}
    for name, ticker in config.SYMBOLS.items():
        price = data_feed.get_current_price(ticker)
        if price:
            current_prices[name] = price
    trading_engine.check_and_resolve_trades(current_prices)

    # Scan for new signals
    for name, ticker in config.SYMBOLS.items():
        df = data_feed.get_data(name, ticker, config.PRIMARY_TIMEFRAME)
        if df is not None and len(df) >= 50:
            signal = signal_engine.analyze(name, df, config.PRIMARY_TIMEFRAME)
            if signal:
                signals_found.append(signal)

                # Auto-execute if enabled
                if st.session_state.auto_trade:
                    trading_engine.process_signal(signal)

    st.session_state.signals_history = signals_found
    st.session_state.last_scan = datetime.now().strftime("%H:%M:%S")
    return signals_found


if scan_btn:
    with st.spinner("Scanning markets..."):
        scan_markets()
    st.rerun()


# ─────────────────────────────────────────────────
#  MAIN HEADER
# ─────────────────────────────────────────────────
col_title, col_status = st.columns([3, 1])
with col_title:
    st.markdown(
        "<h1 style='margin-bottom:0;'>📊 Binary Options Trading Bot</h1>"
        "<p style='color:#64748b; margin-top:0;'>"
        "Real-time signal analysis with strict risk management</p>",
        unsafe_allow_html=True,
    )
with col_status:
    if st.session_state.auto_trade:
        st.markdown(
            "<div style='text-align:right; padding-top:20px;'>"
            "<span style='color:#22c55e; font-size:1.5rem;'>●</span> "
            "<span style='color:#22c55e; font-weight:600;'>AUTO MODE</span>"
            "</div>",
            unsafe_allow_html=True,
        )
    last = st.session_state.last_scan or "Never"
    st.markdown(
        f"<p style='text-align:right; color:#64748b; font-size:0.8rem; "
        f"padding-top:5px;'>Last scan: {last}</p>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────
#  KEY METRICS ROW
# ─────────────────────────────────────────────────
stats = get_te().get_stats()
rm_status = get_rm().get_status()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("💰 Balance", f"${rm_status['balance']:.2f}",
          f"{rm_status['balance_change_pct']:+.1f}%")
m2.metric("📊 Total Trades", stats["total_trades"])
m3.metric("🎯 Win Rate", f"{stats['win_rate']:.0f}%")
m4.metric("💵 Total P&L", format_currency(stats["total_pnl"]),
          f"{'🟢' if stats['total_pnl'] >= 0 else '🔴'}")
m5.metric("⚡ Active", f"{stats['active_count']}/{config.MAX_OPEN_TRADES}")

st.markdown("---")

# ─────────────────────────────────────────────────
#  TABS
# ─────────────────────────────────────────────────
tab_signals, tab_trades, tab_risk, tab_performance = st.tabs([
    "📡 Live Signals", "📋 Trades", "🛡️ Risk Dashboard", "📈 Performance"
])

# ─── TAB 1: LIVE SIGNALS ───
with tab_signals:
    st.markdown("### 📡 Current Market Signals")

    if st.session_state.signals_history:
        for sig in st.session_state.signals_history:
            direction_color = "#22c55e" if sig.direction == "CALL" else "#ef4444"
            direction_icon = "🟢 CALL ↑" if sig.direction == "CALL" else "🔴 PUT ↓"
            conf_color = "#22c55e" if sig.confidence >= 80 else "#f59e0b" if sig.confidence >= 70 else "#94a3b8"

            with st.container():
                sc1, sc2, sc3, sc4 = st.columns([2, 1, 1, 1])
                with sc1:
                    st.markdown(
                        f"<h3 style='margin:0; color:#f1f5f9;'>{sig.symbol}</h3>",
                        unsafe_allow_html=True,
                    )
                with sc2:
                    st.markdown(
                        f"<p style='font-size:1.2rem; font-weight:700; "
                        f"color:{direction_color}; margin:0;'>{direction_icon}</p>",
                        unsafe_allow_html=True,
                    )
                with sc3:
                    st.markdown(
                        f"<p style='font-size:1.2rem; font-weight:700; "
                        f"color:{conf_color}; margin:0;'>"
                        f"🎯 {sig.confidence:.0f}%</p>",
                        unsafe_allow_html=True,
                    )
                with sc4:
                    st.markdown(
                        f"<p style='color:#94a3b8; margin:0;'>"
                        f"@ {sig.price:.5f}</p>",
                        unsafe_allow_html=True,
                    )

                # Indicator breakdown
                with st.expander(f"📊 Indicator Details — {sig.symbol}"):
                    ind_data = []
                    for ind_name, ind_info in sig.indicators.items():
                        ind_data.append({
                            "Indicator": ind_name.upper().replace("_", " "),
                            "Score": f"{ind_info['score']:.0f}",
                            "Direction": ind_info["direction"],
                            "Weight": f"{config.INDICATOR_WEIGHTS.get(ind_name, 0)*100:.0f}%",
                        })
                    st.dataframe(
                        pd.DataFrame(ind_data),
                        use_container_width=True,
                        hide_index=True,
                    )

                # Manual trade button
                if not st.session_state.auto_trade:
                    if st.button(f"Execute {sig.direction} on {sig.symbol}",
                                 key=f"exec_{sig.symbol}"):
                        trade = get_te().process_signal(sig)
                        if trade:
                            st.success(
                                f"Trade #{trade.id} opened: {trade.direction} "
                                f"{trade.symbol} @ {trade.entry_price:.5f} "
                                f"| Stake: ${trade.stake:.2f}"
                            )
                        else:
                            st.error("Trade blocked by risk management")
                        st.rerun()

            st.markdown("---")
    else:
        st.info("🔍 No signals detected. Click **Scan Now** to analyze markets.")

    # Signal log
    signal_log = get_te().get_signal_log()
    if signal_log:
        st.markdown("### 📋 Signal Log")
        st.dataframe(
            pd.DataFrame(signal_log),
            use_container_width=True,
            hide_index=True,
        )

# ─── TAB 2: TRADES ───
with tab_trades:
    # Active trades
    st.markdown("### ⚡ Active Trades")
    active = get_te().get_active_trades_data()
    if active:
        st.dataframe(
            pd.DataFrame(active),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No active trades")

    st.markdown("---")

    # Completed trades
    st.markdown("### 📜 Trade History")
    completed = get_te().get_completed_trades_data()
    if completed:
        df_completed = pd.DataFrame(completed)
        st.dataframe(df_completed, use_container_width=True, hide_index=True)
    else:
        st.info("No completed trades yet. Scan markets and execute trades to see history.")


# ─── TAB 3: RISK DASHBOARD ───
with tab_risk:
    st.markdown("### 🛡️ Risk Management Dashboard")

    status = get_rm().get_status()

    # Risk rules status cards
    r1, r2, r3 = st.columns(3)

    with r1:
        # Position sizing
        st.markdown("#### 💲 Position Sizing")
        st.markdown(f"**Max Risk:** {config.MAX_RISK_PER_TRADE*100:.0f}% per trade")
        st.markdown(f"**Current Stake:** ${status['trade_amount']:.2f}")
        st.markdown(f"**Of Balance:** ${status['balance']:.2f}")

    with r2:
        # Daily loss
        st.markdown("#### 📉 Daily Loss Limit")
        daily = status["daily"]
        loss_pct = daily["loss_pct"]
        max_loss = daily["max_daily_loss_pct"]
        if loss_pct >= max_loss:
            st.error(f"🛑 LIMIT REACHED: {loss_pct:.1f}% / {max_loss:.0f}%")
        elif loss_pct >= max_loss * 0.7:
            st.warning(f"⚠️ WARNING: {loss_pct:.1f}% / {max_loss:.0f}%")
        else:
            st.success(f"✅ OK: {loss_pct:.1f}% / {max_loss:.0f}%")
        st.progress(min(1.0, loss_pct / max_loss) if max_loss > 0 else 0)

    with r3:
        # Consecutive losses
        st.markdown("#### 🔴 Loss Streak")
        streak = daily["consecutive_losses"]
        max_streak = daily["max_consecutive"]
        if streak >= max_streak:
            st.error(f"🛑 COOLDOWN: {streak}/{max_streak}")
        elif streak >= max_streak - 1:
            st.warning(f"⚠️ NEAR LIMIT: {streak}/{max_streak}")
        else:
            st.success(f"✅ OK: {streak}/{max_streak}")

        if status["cooldown_active"]:
            st.markdown(f"⏸️ **Cooldown Until:** {status['cooldown_until']}")

    st.markdown("---")

    r4, r5 = st.columns(2)

    with r4:
        # Open trades
        st.markdown("#### 📊 Open Positions")
        ot = status["open_trades"]
        max_ot = status["max_open_trades"]
        if ot >= max_ot:
            st.warning(f"⚠️ MAX REACHED: {ot}/{max_ot}")
        else:
            st.success(f"✅ {ot}/{max_ot} positions")

    with r5:
        # Minimum balance
        st.markdown("#### 💰 Balance Floor")
        min_bal = status["min_balance"]
        if status["balance"] <= min_bal:
            st.error(f"🛑 BELOW MINIMUM: ${status['balance']:.2f} < ${min_bal:.2f}")
        elif status["balance"] <= min_bal * 1.5:
            st.warning(f"⚠️ LOW: ${status['balance']:.2f} (min: ${min_bal:.2f})")
        else:
            st.success(f"✅ ${status['balance']:.2f} (min: ${min_bal:.2f})")

    st.markdown("---")

    # Risk rules summary
    st.markdown("### 📏 Risk Rules Reference")
    rules_data = [
        {"Rule": "Max Risk Per Trade", "Setting": f"{config.MAX_RISK_PER_TRADE*100:.0f}%", "Current": f"${status['trade_amount']:.2f}"},
        {"Rule": "Max Daily Loss", "Setting": f"{config.MAX_DAILY_LOSS*100:.0f}%", "Current": f"{daily['loss_pct']:.1f}%"},
        {"Rule": "Max Consecutive Losses", "Setting": str(config.MAX_CONSECUTIVE_LOSSES), "Current": str(daily["consecutive_losses"])},
        {"Rule": "Cooldown Duration", "Setting": f"{config.COOLDOWN_MINUTES} min", "Current": "Active" if status["cooldown_active"] else "Inactive"},
        {"Rule": "Max Open Trades", "Setting": str(config.MAX_OPEN_TRADES), "Current": str(status["open_trades"])},
        {"Rule": "Minimum Balance", "Setting": f"${min_bal:.2f}", "Current": f"${status['balance']:.2f}"},
    ]
    st.dataframe(pd.DataFrame(rules_data), use_container_width=True, hide_index=True)


# ─── TAB 4: PERFORMANCE ───
with tab_performance:
    st.markdown("### 📈 Performance Analytics")

    equity_data = get_rm().get_equity_curve()

    if len(equity_data) > 1:
        # Equity curve
        eq_df = pd.DataFrame(equity_data)
        fig_equity = go.Figure()
        fig_equity.add_trace(go.Scatter(
            x=eq_df["trade"],
            y=eq_df["balance"],
            mode="lines+markers",
            name="Balance",
            line=dict(color="#0ea5e9", width=3),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(14, 165, 233, 0.1)",
        ))
        fig_equity.add_hline(
            y=config.INITIAL_BALANCE, line_dash="dash",
            line_color="#f59e0b", annotation_text="Starting Balance"
        )
        fig_equity.update_layout(
            title="Equity Curve",
            xaxis_title="Trade #",
            yaxis_title="Balance ($)",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
        )
        st.plotly_chart(fig_equity, use_container_width=True)

        # Win/Loss distribution
        completed = get_te().completed_trades
        if completed:
            pc1, pc2 = st.columns(2)

            with pc1:
                wins = sum(1 for t in completed if t.result == "WIN")
                losses = sum(1 for t in completed if t.result == "LOSS")
                fig_wl = go.Figure(data=[go.Pie(
                    labels=["Wins", "Losses"],
                    values=[wins, losses],
                    hole=0.6,
                    marker_colors=["#22c55e", "#ef4444"],
                )])
                fig_wl.update_layout(
                    title="Win/Loss Ratio",
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    height=350,
                )
                st.plotly_chart(fig_wl, use_container_width=True)

            with pc2:
                # P&L per trade
                pnl_data = [t.pnl for t in completed]
                colors = ["#22c55e" if p > 0 else "#ef4444" for p in pnl_data]
                fig_pnl = go.Figure(data=[go.Bar(
                    x=list(range(1, len(pnl_data) + 1)),
                    y=pnl_data,
                    marker_color=colors,
                )])
                fig_pnl.update_layout(
                    title="P&L Per Trade",
                    xaxis_title="Trade #",
                    yaxis_title="P&L ($)",
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    height=350,
                )
                st.plotly_chart(fig_pnl, use_container_width=True)
    else:
        st.info("📊 Performance charts will appear after your first trade.")

    # Summary stats
    if stats["total_trades"] > 0:
        st.markdown("### 📊 Summary Statistics")
        ss1, ss2, ss3, ss4 = st.columns(4)
        ss1.metric("Best Trade", format_currency(stats["best_trade"]))
        ss2.metric("Worst Trade", format_currency(stats["worst_trade"]))
        avg_pnl = stats["total_pnl"] / stats["total_trades"] if stats["total_trades"] > 0 else 0
        ss3.metric("Avg Trade", format_currency(avg_pnl))
        profit_factor = (
            abs(sum(t.pnl for t in get_te().completed_trades if t.pnl > 0)) /
            abs(sum(t.pnl for t in get_te().completed_trades if t.pnl < 0))
            if any(t.pnl < 0 for t in get_te().completed_trades)
            else float("inf")
        )
        ss4.metric("Profit Factor", f"{profit_factor:.2f}" if profit_factor != float("inf") else "∞")


# ─────────────────────────────────────────────────
#  AUTO-REFRESH
# ─────────────────────────────────────────────────
if st.session_state.auto_trade:
    time.sleep(config.REFRESH_INTERVAL_SECONDS)
    scan_markets()
    st.rerun()
