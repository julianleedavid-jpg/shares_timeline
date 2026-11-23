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


def clean_tickers(raw_items) -> list[str]:
    """Normalizes, deduplicates, and sorts a list/iterable of ticker symbols."""
    cleaned = set()
    for item in raw_items:
        token = str(item).strip().upper()
        if token and token not in {"TICKER", "SYMBOL", "TICKERS", "SYMBOLS"}:
            cleaned.add(token)
    return sorted(cleaned)


def load_watchlists() -> dict[str, list[str]]:
    """Loads watchlists dictionary from local JSON file."""
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {"Main Watchlist": clean_tickers(data)}
            if isinstance(data, dict) and data:
                loaded = {
                    str(k).strip(): clean_tickers(v if isinstance(v, list) else [])
                    for k, v in data.items()
                    if str(k).strip()
                }
                if loaded:
                    return loaded
        except Exception:
            pass
    return {k: clean_tickers(v) for k, v in DEFAULT_WATCHLISTS.items()}


def save_watchlists(watchlists: dict[str, list[str]]) -> bool:
    """Saves watchlists dictionary to local JSON file; returns False if disk is read-only."""
    sorted_watchlists = {k: clean_tickers(v) for k, v in watchlists.items()}
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted_watchlists, f, indent=4)
        return True
    except OSError:
        return False


def parse_imported_tickers(uploaded_file, pasted_text: str) -> list[str]:
    """Extracts ticker symbols from an uploaded CSV/TXT/JSON file or pasted text."""
    extracted: list[str] = []

    if uploaded_file is not None:
        filename = uploaded_file.name.lower()
        raw_bytes = uploaded_file.getvalue()
        text_content = raw_bytes.decode("utf-8", errors="ignore")

        if filename.endswith(".json"):
            parsed = json.loads(text_content)
            if isinstance(parsed, list):
                extracted.extend(parsed)
            elif isinstance(parsed, dict):
                for val in parsed.values():
                    if isinstance(val, list):
                        extracted.extend(val)
        elif filename.endswith(".csv"):
            df = pd.read_csv(pd.io.common.StringIO(text_content))
            if not df.empty:
                target_col = None
                for col in df.columns:
                    if str(col).strip().lower() in {"ticker", "tickers", "symbol", "symbols"}:
                        target_col = col
                        break
                series = df[target_col] if target_col is not None else df.iloc[:, 0]
                for val in series.dropna().astype(str):
                    for part in val.replace("\n", ",").split(","):
                        extracted.append(part)
        else:
            for line in text_content.replace("\r\n", "\n").split("\n"):
                for part in line.split(","):
                    extracted.append(part)

    if pasted_text and pasted_text.strip():
        for line in pasted_text.replace("\r\n", "\n").split("\n"):
            for part in line.split(","):
                extracted.append(part)

    return clean_tickers(extracted)


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

if "watchlists" not in st.session_state:
    st.session_state.watchlists = load_watchlists()

wl_names = list(st.session_state.watchlists.keys())
if "active_watchlist" not in st.session_state or st.session_state.active_watchlist not in wl_names:
    st.session_state.active_watchlist = wl_names[0]

# --- WATCHLIST SELECTION & MANAGEMENT ---
col_w1, col_w2, col_w3 = st.columns([1.2, 2.2, 1.3])
with col_w1:
    selected_wl = st.selectbox(
        "Watchlist",
        options=wl_names,
        index=wl_names.index(st.session_state.active_watchlist),
    )
    st.session_state.active_watchlist = selected_wl

wl_tickers = st.session_state.watchlists.get(selected_wl, [])
with col_w2:
    selected_tickers = st.multiselect(
        f"Shares in '{selected_wl}'",
        options=wl_tickers,
        default=wl_tickers,
    )

with col_w3:
    extra_raw = st.text_input(
        "Temporary Compare Tickers (optional)",
        value="",
        placeholder="e.g., NVDA, AZN.L",
    )

with st.expander("🗂️ Manage Watchlists, Add/Remove Tickers & Import/Export", expanded=False):
    m_col1, m_col2, m_col3 = st.columns(3)

    # 1. Create / Delete Watchlists
    with m_col1:
        st.markdown("**Watchlists**")
        new_wl_name = st.text_input("New Watchlist Name", placeholder="e.g., UK Income")
        if st.button("Create Watchlist"):
            clean_name = new_wl_name.strip()
            if not clean_name:
                st.warning("Enter a watchlist name.")
            elif clean_name in st.session_state.watchlists:
                st.warning(f"'{clean_name}' already exists.")
            else:
                st.session_state.watchlists[clean_name] = []
                st.session_state.active_watchlist = clean_name
                save_watchlists(st.session_state.watchlists)
                st.rerun()

        if len(st.session_state.watchlists) > 1:
            if st.button(f"Delete '{selected_wl}'"):
                del st.session_state.watchlists[selected_wl]
                st.session_state.active_watchlist = list(st.session_state.watchlists.keys())[0]
                save_watchlists(st.session_state.watchlists)
                st.rerun()

    # 2. Add / Remove Tickers in Active Watchlist
    with m_col2:
        st.markdown(f"**Edit '{selected_wl}' Tickers**")
        add_ticker_raw = st.text_input(
            "Add Ticker(s)", placeholder="e.g., VOD.L or AAPL, MSFT"
        )
        if st.button("Add Ticker(s)"):
            to_add = [t.strip().upper() for t in add_ticker_raw.replace("\n", ",").split(",") if t.strip()]
            if to_add:
                updated = clean_tickers(st.session_state.watchlists[selected_wl] + to_add)
                st.session_state.watchlists[selected_wl] = updated
                save_watchlists(st.session_state.watchlists)
                st.rerun()

        if wl_tickers:
            tickers_to_remove = st.multiselect(
                "Remove Ticker(s)", options=wl_tickers, default=[]
            )
            if st.button("Remove Selected Ticker(s)") and tickers_to_remove:
                remaining = [t for t in st.session_state.watchlists[selected_wl] if t not in tickers_to_remove]
                st.session_state.watchlists[selected_wl] = remaining
                save_watchlists(st.session_state.watchlists)
                st.rerun()

    # 3. Import / Export Watchlist Tickers
    with m_col3:
        st.markdown("**Import / Export**")
        uploaded_wl_file = st.file_uploader(
            "Import CSV, TXT, or JSON", type=["csv", "txt", "json"]
        )
        pasted_wl_tickers = st.text_area(
            "Or Paste Tickers", height=68, placeholder="AAPL, MSFT, SHEL.L"
        )
        import_mode = st.radio(
            "Import Action",
            options=["Merge into active", "Replace active", "Create new watchlist"],
            horizontal=False,
        )
        target_import_wl = st.text_input(
            "New Watchlist Name (if creating new)", placeholder="Imported Watchlist"
        )
        if st.button("Import Tickers"):
            try:
                imported = parse_imported_tickers(uploaded_wl_file, pasted_wl_tickers)
                if not imported:
                    st.warning("No valid tickers found to import.")
                elif import_mode == "Create new watchlist":
                    wl_target = target_import_wl.strip() or (
                        uploaded_wl_file.name.rsplit(".", 1)[0]
                        if uploaded_wl_file
                        else "Imported Watchlist"
                    )
                    existing = st.session_state.watchlists.get(wl_target, [])
                    st.session_state.watchlists[wl_target] = clean_tickers(existing + imported)
                    st.session_state.active_watchlist = wl_target
                    save_watchlists(st.session_state.watchlists)
                    st.rerun()
                elif import_mode == "Replace active":
                    st.session_state.watchlists[selected_wl] = imported
                    save_watchlists(st.session_state.watchlists)
                    st.rerun()
                else:
                    st.session_state.watchlists[selected_wl] = clean_tickers(
                        st.session_state.watchlists[selected_wl] + imported
                    )
                    save_watchlists(st.session_state.watchlists)
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not import tickers: {exc}")

        slug_name = selected_wl.lower().replace(" ", "_")
        csv_export = pd.DataFrame({"Ticker": wl_tickers}).to_csv(index=False).encode("utf-8")
        json_export = json.dumps({selected_wl: wl_tickers}, indent=4).encode("utf-8")

        exp_c1, exp_c2 = st.columns(2)
        with exp_c1:
            st.download_button(
                "Export CSV",
                data=csv_export,
                file_name=f"{slug_name}_tickers.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with exp_c2:
            st.download_button(
                "Export JSON",
                data=json_export,
                file_name=f"{slug_name}_tickers.json",
                mime="application/json",
                use_container_width=True,
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
