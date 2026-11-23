from datetime import datetime, timedelta
import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

WATCHLIST_FILE = "watchlist.json"
DEFAULT_WATCHLISTS = {
    "Main Watchlist": [
        "AAPL",
        "MSFT",
        "SHEL.L",
        "LLOY.L",
        "UKW.L",
        "BLND.L",
        "RIO.L",
        "DUKE.L",
    ],
}

TIMELINE_PRESETS = {
    "1 Day": {"period": "1d", "interval": "5m"},
    "1 Week": {"period": "5d", "interval": "15m"},
    "1 Month": {"period": "1mo", "interval": "1d"},
    "3 Months": {"period": "3mo", "interval": "1d"},
    "6 Months": {"period": "6mo", "interval": "1d"},
    "1 Year": {"period": "1y", "interval": "1d"},
    "2 Years": {"period": "2y", "interval": "1d"},
    "3 Years": {"period": "3y", "interval": "1d"},
    "5 Years": {"period": "5y", "interval": "1wk"},
    "All Time": {"period": "max", "interval": "1mo"},
    "Custom": None,
}


def load_watchlists() -> dict:
    """Loads watchlists dictionary from local JSON file."""
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {"Main Watchlist": sorted(data)}
            if isinstance(data, dict) and data:
                return {k: sorted(v) for k, v in data.items()}
        except Exception:
            return {k: sorted(v) for k, v in DEFAULT_WATCHLISTS.items()}
    return {k: sorted(v) for k, v in DEFAULT_WATCHLISTS.items()}


@st.cache_data(ttl=300)
def fetch_timeline_prices(
    ticker_list: list[str], tf: str, start_dt=None, end_dt=None
) -> pd.DataFrame:
    """Fetches historical close prices for multiple tickers on a unified timeline."""
    if not ticker_list:
        return pd.DataFrame()

    if tf == "Custom":
        if not start_dt or not end_dt or start_dt >= end_dt:
            return pd.DataFrame()
        data = yf.download(
            ticker_list,
            start=start_dt,
            end=end_dt + timedelta(days=1),
            progress=False,
            auto_adjust=True,
        )
    elif tf == "3 Years":
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365 * 3)
        data = yf.download(
            ticker_list,
            start=start_date,
            end=end_date + timedelta(days=1),
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
    else:
        cfg = TIMELINE_PRESETS[tf]
        data = yf.download(
            ticker_list,
            period=cfg["period"],
            interval=cfg["interval"],
            progress=False,
            auto_adjust=True,
        )

    if data is None or data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        closes = data["Close"].copy()
    else:
        closes = data[["Close"]].rename(columns={"Close": ticker_list[0]}).copy()

    # Convert UK pence (.L) prices from GBX to GBP for consistent comparison
    for col in closes.columns:
        if str(col).upper().endswith(".L"):
            closes[col] = closes[col] / 100.0

    return closes.dropna(how="all")


st.set_page_config(
    page_title="Watchlist Share Price Timeline",
    page_icon="📊",
    layout="wide",
)
st.title("📊 Watchlist Share Price Timeline")

watchlists = load_watchlists()
wl_names = list(watchlists.keys())

col_w1, col_w2, col_w3 = st.columns([1.2, 2.2, 1.3])
with col_w1:
    selected_wl = st.selectbox("Watchlist", options=wl_names, index=0)

wl_tickers = watchlists.get(selected_wl, [])
with col_w2:
    selected_tickers = st.multiselect(
        f"Shares in '{selected_wl}'",
        options=wl_tickers,
        default=wl_tickers,
    )

with col_w3:
    extra_raw = st.text_input(
        "Extra Tickers (optional)",
        value="",
        placeholder="e.g., NVDA, AZN.L",
    )

extra_tickers = [t.strip().upper() for t in extra_raw.split(",") if t.strip()]
tickers = list(dict.fromkeys(selected_tickers + extra_tickers))

col_p1, col_p2 = st.columns([3, 1])
with col_p1:
    selected_tf = st.radio(
        "Timeline",
        options=list(TIMELINE_PRESETS.keys()),
        index=5,  # Default: 1 Year
        horizontal=True,
    )
with col_p2:
    scale_mode = st.selectbox(
        "Y-Axis Scale",
        options=["Normalized (% Change)", "Actual Price"],
    )

start_dt, end_dt = None, None
if selected_tf == "Custom":
    today = datetime.today().date()
    c_s, c_e = st.columns(2)
    with c_s:
        start_dt = st.date_input("Start Date", value=today - timedelta(days=180))
    with c_e:
        end_dt = st.date_input("End Date", value=today)

if not tickers:
    st.info("Select at least one share from your watchlist or enter a ticker.")
    st.stop()

prices = fetch_timeline_prices(tickers, selected_tf, start_dt, end_dt)
if prices.empty:
    st.warning("No price data available for the selected tickers or timeline.")
    st.stop()

if scale_mode == "Normalized (% Change)":
    plot_df = pd.DataFrame(index=prices.index)
    for col in prices.columns:
        s = prices[col].dropna()
        if not s.empty:
            plot_df[col] = ((prices[col] - s.iloc[0]) / s.iloc[0]) * 100.0
    y_label = "Return (%)"
    hover_fmt = "%{y:+.2f}%"
else:
    plot_df = prices
    y_label = "Price (USD / GBP)"
    hover_fmt = "%{y:,.2f}"

fig = go.Figure()
for col in plot_df.columns:
    fig.add_trace(
        go.Scatter(
            x=plot_df.index,
            y=plot_df[col],
            mode="lines",
            name=col,
            connectgaps=True,
            hovertemplate=f"<b>{col}</b><br>%{{x}}<br>{hover_fmt}<extra></extra>",
        )
    )

fig.update_layout(
    hovermode="x unified",
    xaxis_title="Date / Time",
    yaxis_title=y_label,
    height=520,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Period Performance Summary")
summary_rows = []
for col in prices.columns:
    s = prices[col].dropna()
    if len(s) >= 2:
        start_p = float(s.iloc[0])
        end_p = float(s.iloc[-1])
        diff = end_p - start_p
        pct = (diff / start_p) * 100.0 if start_p else 0.0
        curr_prefix = "£" if str(col).upper().endswith(".L") else "$"
        summary_rows.append(
            {
                "Ticker": col,
                "Currency": curr_prefix,
                "Start Price": round(start_p, 2),
                "Latest Price": round(end_p, 2),
                "Change": round(diff, 2),
                "Change (%)": round(pct, 2),
                "Period Low": round(float(s.min()), 2),
                "Period High": round(float(s.max()), 2),
            }
        )

if summary_rows:
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
