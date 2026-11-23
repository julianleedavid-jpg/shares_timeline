from datetime import datetime, timedelta
import io
import json
import os
import time

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

WATCHLIST_FILE = "watchlist.json"
SECTOR_OVERRIDES_FILE = "sector_overrides.json"

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

FTSE100_PRESET_TICKERS = [
    "III.L", "ABDN.L", "ADM.L", "AAF.L", "ALW.L", "AAL.L", "ANTO.L", "ABF.L",
    "AZN.L", "AUTO.L", "AV.L", "BAB.L", "BA.L", "BBY.L", "BARC.L", "BTRW.L",
    "BP.L", "BATS.L", "BLND.L", "BT-A.L", "BNZL.L", "CNA.L", "CCH.L", "CCEP.L",
    "CPG.L", "DGE.L", "DPLM.L", "EDV.L", "ENT.L", "EXPN.L", "FCIT.L", "FRES.L",
    "GLEN.L", "GSK.L", "HLN.L", "HLMA.L", "HSX.L", "HSBA.L", "IMI.L", "IMB.L",
    "INF.L", "IHG.L", "IAG.L", "ITRK.L", "KGF.L", "LAND.L", "LGEN.L", "LLOY.L",
    "LSEG.L", "MNG.L", "MKS.L", "MRO.L", "NG.L", "NXT.L", "PCT.L", "PSON.L",
    "PRU.L", "RKT.L", "REL.L", "RTO.L", "RIO.L", "RR.L", "SGE.L", "SBRY.L",
    "SMT.L", "SGRO.L", "SVT.L", "SHEL.L", "SMIN.L", "SN.L", "SSE.L", "STAN.L",
    "SDLF.L", "TSCO.L", "ULVR.L", "UU.L", "VOD.L", "WEIR.L",
]

SP500_PRESET_TICKERS = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AES", "AFL", "A", "APD",
    "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG",
    "MO", "AMZN", "AMCR", "AMD", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK",
    "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT",
    "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO",
    "NVDA", "BRK-B", "TSLA", "UNH", "LLY", "JPM", "XOM", "JNJ", "V", "PG",
    "AVGO", "META", "HD", "CVX", "MRK", "PEP", "COST", "KO", "CSCO", "WMT",
    "TMO", "MCD", "PFE", "CRM", "BAC", "CMCSA", "LIN", "NFLX", "ORCL", "DHR",
    "WFC", "DIS", "TXN", "PM", "VZ", "INTU", "COP", "CAT", "UNP", "LOW",
    "IBM", "BMY", "SPGI", "RTX", "HON", "BA", "UPS", "GE", "QCOM", "NKE",
    "PLD", "NOW", "BKNG", "SBUX", "MS", "ELV", "MDT", "GS", "DE", "ADP",
    "LMT", "TJX", "BLK", "ISRG", "MDLZ", "GILD", "MMC", "SYK", "REGN", "VRTX",
    "ETN", "LRCX", "SCHW", "CVS", "ZTS", "CI", "CB", "MU", "PLTR", "PANW",
    "GEV", "DELL", "C", "WELL", "KLAC", "VYLR", "TWLO", "OKTA", "BE", "P",
    "ILMN", "RDDT", "FERG", "HONA", "MRVL", "FLEX", "FDXF",
]

KNOWN_TICKER_SECTORS = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "AVGO": "Technology",
    "ORCL": "Technology", "CRM": "Technology", "INTU": "Technology", "ADBE": "Technology",
    "CSCO": "Technology", "IBM": "Technology", "QCOM": "Technology", "NOW": "Technology",
    "TXN": "Technology", "ADI": "Technology", "AMAT": "Technology", "LRCX": "Technology",
    "KLAC": "Technology", "MRVL": "Technology", "PLTR": "Technology", "PANW": "Technology",
    "APH": "Technology", "ANET": "Technology", "AKAM": "Technology", "TWLO": "Technology",
    "OKTA": "Technology", "DELL": "Technology", "ALW.L": "Technology", "AUTO.L": "Technology",
    "SGE.L": "Technology",
    # Communication Services
    "GOOGL": "Communication Services", "GOOG": "Communication Services",
    "META": "Communication Services", "NFLX": "Communication Services",
    "DIS": "Communication Services", "CMCSA": "Communication Services",
    "VZ": "Communication Services", "T": "Communication Services",
    "RDDT": "Communication Services", "VOD.L": "Communication Services",
    "BT-A.L": "Communication Services",
    # Consumer Cyclical
    "AMZN": "Consumer Cyclical", "TSLA": "Consumer Cyclical", "HD": "Consumer Cyclical",
    "MCD": "Consumer Cyclical", "LOW": "Consumer Cyclical", "BKNG": "Consumer Cyclical",
    "SBUX": "Consumer Cyclical", "NKE": "Consumer Cyclical", "TJX": "Consumer Cyclical",
    "ABNB": "Consumer Cyclical", "APTV": "Consumer Cyclical", "BOWL.L": "Consumer Cyclical",
    "BWY.L": "Consumer Cyclical", "BTRW.L": "Consumer Cyclical", "ENT.L": "Consumer Cyclical",
    "IHG.L": "Consumer Cyclical", "KGF.L": "Consumer Cyclical", "NXT.L": "Consumer Cyclical",
    "PSON.L": "Consumer Cyclical",
    # Consumer Defensive
    "PG": "Consumer Defensive", "COST": "Consumer Defensive", "WMT": "Consumer Defensive",
    "KO": "Consumer Defensive", "PEP": "Consumer Defensive", "PM": "Consumer Defensive",
    "MO": "Consumer Defensive", "MDLZ": "Consumer Defensive", "CL": "Consumer Defensive",
    "ULVR.L": "Consumer Defensive", "DGE.L": "Consumer Defensive", "TSCO.L": "Consumer Defensive",
    "ABF.L": "Consumer Defensive", "BATS.L": "Consumer Defensive", "CCH.L": "Consumer Defensive",
    "CCEP.L": "Consumer Defensive", "CPG.L": "Consumer Defensive", "IMB.L": "Consumer Defensive",
    "MKS.L": "Consumer Defensive", "RKT.L": "Consumer Defensive", "SBRY.L": "Consumer Defensive",
    # Financial Services
    "BRK-B": "Financial Services", "JPM": "Financial Services", "V": "Financial Services",
    "BAC": "Financial Services", "WFC": "Financial Services", "MS": "Financial Services",
    "GS": "Financial Services", "BLK": "Financial Services", "AXP": "Financial Services",
    "SPGI": "Financial Services", "SCHW": "Financial Services", "MMC": "Financial Services",
    "CB": "Financial Services", "PGR": "Financial Services", "AFL": "Financial Services",
    "AIG": "Financial Services", "AMP": "Financial Services", "AON": "Financial Services",
    "AJG": "Financial Services", "AIZ": "Financial Services", "ACGL": "Financial Services",
    "APO": "Financial Services", "ARES": "Financial Services", "C": "Financial Services",
    "AV.L": "Financial Services", "BARC.L": "Financial Services", "LLOY.L": "Financial Services",
    "NWG.L": "Financial Services", "HSBA.L": "Financial Services", "LGEN.L": "Financial Services",
    "MNG.L": "Financial Services", "SDLF.L": "Financial Services", "DUKE.L": "Financial Services",
    "III.L": "Financial Services", "ABDN.L": "Financial Services", "ADM.L": "Financial Services",
    "HSX.L": "Financial Services", "LSEG.L": "Financial Services", "PRU.L": "Financial Services",
    "SDR.L": "Financial Services", "SMT.L": "Financial Services", "STAN.L": "Financial Services",
    "FCIT.L": "Financial Services", "PCT.L": "Financial Services",
    # Healthcare
    "UNH": "Healthcare", "LLY": "Healthcare", "JNJ": "Healthcare", "ABBV": "Healthcare",
    "MRK": "Healthcare", "TMO": "Healthcare", "ABT": "Healthcare", "PFE": "Healthcare",
    "DHR": "Healthcare", "BMY": "Healthcare", "AMGN": "Healthcare", "ELV": "Healthcare",
    "MDT": "Healthcare", "ISRG": "Healthcare", "GILD": "Healthcare", "SYK": "Healthcare",
    "REGN": "Healthcare", "VRTX": "Healthcare", "CVS": "Healthcare", "ZTS": "Healthcare",
    "CI": "Healthcare", "ALGN": "Healthcare", "A": "Healthcare", "ILMN": "Healthcare",
    "GSK.L": "Healthcare", "AZN.L": "Healthcare", "HLN.L": "Healthcare",
    "HLMA.L": "Healthcare", "SN.L": "Healthcare",
    # Industrials
    "CAT": "Industrials", "GE": "Industrials", "RTX": "Industrials", "HON": "Industrials",
    "UNP": "Industrials", "BA": "Industrials", "UPS": "Industrials", "DE": "Industrials",
    "ADP": "Industrials", "LMT": "Industrials", "ETN": "Industrials", "GEV": "Industrials",
    "MMM": "Industrials", "AOS": "Industrials", "ALLE": "Industrials", "AME": "Industrials",
    "FERG": "Industrials", "FLEX": "Industrials", "FDXF": "Industrials",
    "RR.L": "Industrials", "BA.L": "Industrials", "BAB.L": "Industrials",
    "BNZL.L": "Industrials", "DPLM.L": "Industrials", "EXPN.L": "Industrials",
    "IMI.L": "Industrials", "INF.L": "Industrials", "ITRK.L": "Industrials",
    "REL.L": "Industrials", "RTO.L": "Industrials", "SMIN.L": "Industrials",
    "WEIR.L": "Industrials", "AAF.L": "Industrials", "BBY.L": "Industrials",
    "MRO.L": "Industrials",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "APA": "Energy",
    "SHEL.L": "Energy", "BP.L": "Energy",
    # Basic Materials
    "LIN": "Basic Materials", "APD": "Basic Materials", "ALB": "Basic Materials",
    "AMCR": "Basic Materials", "RIO.L": "Basic Materials", "GLEN.L": "Basic Materials",
    "AAL.L": "Basic Materials", "ANTO.L": "Basic Materials", "EDV.L": "Basic Materials",
    "FRES.L": "Basic Materials",
    # Utilities
    "NEE": "Utilities", "SO": "Utilities", "DUK": "Utilities", "AEP": "Utilities",
    "SRE": "Utilities", "AES": "Utilities", "LNT": "Utilities", "AEE": "Utilities",
    "AMT": "Real Estate", "AWK": "Utilities", "ATO": "Utilities", "BE": "Utilities",
    "NG.L": "Utilities", "UKW.L": "Utilities", "SSE.L": "Utilities",
    "SVT.L": "Utilities", "UU.L": "Utilities", "CNA.L": "Utilities",
    # Real Estate
    "PLD": "Real Estate", "WELL": "Real Estate", "ARE": "Real Estate",
    "BLND.L": "Real Estate", "LMP.L": "Real Estate", "LAND.L": "Real Estate",
    "SGRO.L": "Real Estate",
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


def normalize_ticker_list(raw_items) -> list[str]:
    """Normalizes, deduplicates (preserving order), and filters header tokens."""
    seen: set[str] = set()
    result: list[str] = []
    for item in raw_items:
        token = str(item).strip().upper()
        if (
            token
            and token not in {"TICKER", "SYMBOL", "TICKERS", "SYMBOLS"}
            and token not in seen
        ):
            seen.add(token)
            result.append(token)
    return result


def clean_tickers(raw_items) -> list[str]:
    """Returns a sorted, deduplicated list of ticker symbols."""
    return sorted(normalize_ticker_list(raw_items))


@st.cache_data(ttl=86400)
def get_live_ftse100_tickers() -> list[str]:
    """Fetches current FTSE 100 constituents dynamically from Wikipedia, with preset fallback[cite: 2]."""
    url = "https://en.wikipedia.org/wiki/FTSE_100_Index"[cite: 2]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }[cite: 2]
    try:
        response = requests.get(url, headers=headers, timeout=10)[cite: 2]
        response.raise_for_status()[cite: 2]
        tables = pd.read_html(io.StringIO(response.text))[cite: 2]
        for table in tables:
            if "Ticker" in table.columns:
                raw_syms = (
                    table["Ticker"]
                    .astype(str)
                    .str.strip()
                    .str.replace(".", "-", regex=False)
                    + ".L"
                ).tolist()[cite: 2]
                cleaned = clean_tickers(raw_syms)
                if len(cleaned) >= 50:
                    return cleaned
    except Exception:
        pass
    return clean_tickers(FTSE100_PRESET_TICKERS)


@st.cache_data(ttl=86400)
def get_live_sp500_tickers() -> list[str]:
    """Fetches current S&P 500 constituents dynamically from Wikipedia, with preset fallback[cite: 2]."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"[cite: 2]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }[cite: 2]
    try:
        response = requests.get(url, headers=headers, timeout=10)[cite: 2]
        response.raise_for_status()[cite: 2]
        tables = pd.read_html(io.StringIO(response.text))[cite: 2]
        for table in tables:
            if "Symbol" in table.columns:[cite: 2]
                raw_syms = (
                    table["Symbol"]
                    .astype(str)
                    .str.strip()
                    .str.replace(".", "-", regex=False)
                ).tolist()[cite: 2]
                cleaned = clean_tickers(raw_syms)
                if len(cleaned) >= 100:
                    return cleaned
    except Exception:
        pass
    return clean_tickers(SP500_PRESET_TICKERS)


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


def apply_tickers_to_watchlist(
    wl_name: str, candidate_tickers: list[str], mode: str = "merge"
) -> tuple[int, int]:
    """Updates a watchlist with deduplicated tickers; returns (added_count, ignored_dupes)."""
    deduped = normalize_ticker_list(candidate_tickers)
    batch_dupes = len(candidate_tickers) - len(deduped)
    existing = st.session_state.watchlists.get(wl_name, [])

    if mode == "replace":
        st.session_state.watchlists[wl_name] = clean_tickers(deduped)
        save_watchlists(st.session_state.watchlists)
        return len(deduped), batch_dupes

    existing_set = set(existing)
    truly_new = [t for t in deduped if t not in existing_set]
    skipped_dupes = batch_dupes + (len(deduped) - len(truly_new))
    st.session_state.watchlists[wl_name] = clean_tickers(existing + truly_new)
    save_watchlists(st.session_state.watchlists)
    return len(truly_new), skipped_dupes


def load_sector_overrides() -> dict[str, str]:
    """Loads user-saved ticker-to-sector mappings."""
    if os.path.exists(SECTOR_OVERRIDES_FILE):
        try:
            with open(SECTOR_OVERRIDES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {
                    str(k).strip().upper(): str(v).strip()
                    for k, v in data.items()
                    if str(k).strip() and str(v).strip()
                }
        except Exception:
            pass
    return {}


def save_sector_overrides(overrides: dict[str, str]) -> bool:
    """Saves user-edited ticker-to-sector mappings to local JSON."""
    try:
        with open(SECTOR_OVERRIDES_FILE, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(overrides.items())), f, indent=4)
        return True
    except OSError:
        return False


def extract_raw_imported_tokens(uploaded_file, pasted_text: str) -> list[str]:
    """Extracts raw ticker tokens before deduplication from an uploaded file or pasted text."""
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
                    if str(col).strip().lower() in {
                        "ticker",
                        "tickers",
                        "symbol",
                        "symbols",
                    }:
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

    return extracted


@st.cache_data(ttl=86400)
def _fetch_live_sector_cached(symbol: str) -> str | None:
    """Caches only valid live sector strings from yfinance so failures aren't stuck in cache."""
    for attempt in range(2):
        try:
            info = yf.Ticker(symbol).info
            if isinstance(info, dict):
                sector = info.get("sector") or info.get("sectorDisp")
                if sector and str(sector).strip():
                    return str(sector).strip()
        except Exception:
            time.sleep(0.5 * (attempt + 1))

    try:
        search = yf.Search(symbol, max_results=3)
        quotes = getattr(search, "quotes", None) or []
        for q in quotes:
            if str(q.get("symbol", "")).upper() == symbol:
                sec = q.get("sector") or q.get("sectorDisp")
                if sec and str(sec).strip():
                    return str(sec).strip()
    except Exception:
        pass

    return None


def resolve_ticker_sector(
    ticker_symbol: str, overrides: dict[str, str], allow_live_lookup: bool = True
) -> str:
    """Resolves sector via user overrides -> built-in map -> optional live Yahoo lookup -> 'Unclassified'."""
    sym = ticker_symbol.strip().upper()
    if sym in overrides and overrides[sym]:
        return overrides[sym]

    if sym in KNOWN_TICKER_SECTORS:
        return KNOWN_TICKER_SECTORS[sym]

    if allow_live_lookup:
        live_sector = _fetch_live_sector_cached(sym)
        if live_sector:
            return live_sector

    return "Unclassified"


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


def build_sector_averages_df(
    prices_df: pd.DataFrame, sector_map: dict[str, str]
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Groups price columns by sector and computes the row-wise mean share value per sector."""
    sector_groups: dict[str, list[str]] = {}
    for col in prices_df.columns:
        sym = str(col).strip().upper()
        sec = sector_map.get(sym, "Unclassified")
        sector_groups.setdefault(sec, []).append(col)

    sector_series_dict: dict[str, pd.Series] = {}
    sector_ticker_labels: dict[str, str] = {}
    for sec, group_cols in sorted(sector_groups.items()):
        sector_series_dict[sec] = prices_df[group_cols].mean(axis=1, skipna=True)
        sector_ticker_labels[sec] = ", ".join(str(c) for c in group_cols)

    sector_df = pd.DataFrame(sector_series_dict, index=prices_df.index).dropna(
        how="all"
    )
    return sector_df, sector_ticker_labels


def build_line_figure(
    series_df: pd.DataFrame, mode: str, y_label: str, entity_label: str = "Ticker"
) -> go.Figure:
    """Builds a Plotly line chart where hovering a line shows info only for that series."""
    if mode == "Normalized (% Change)":
        plot_df = pd.DataFrame(index=series_df.index)
        for col in series_df.columns:
            s = series_df[col].dropna()
            if not s.empty and float(s.iloc[0]) != 0.0:
                plot_df[col] = (
                    (series_df[col] - float(s.iloc[0])) / float(s.iloc[0])
                ) * 100.0
        hover_fmt = "%{y:+.2f}%"
    else:
        plot_df = series_df
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
                hovertemplate=(
                    f"<b>{entity_label}: {col}</b><br>"
                    f"Date: %{{x}}<br>"
                    f"Value: {hover_fmt}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        hovermode="closest",
        xaxis_title="Date / Time",
        yaxis_title=y_label,
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def build_summary_rows(
    series_df: pd.DataFrame, name_col: str, extra_map: dict[str, str] | None = None
) -> list[dict]:
    """Calculates start, latest, change, percentage change, low, and high across a timeline."""
    rows = []
    for col in series_df.columns:
        s = series_df[col].dropna()
        if len(s) >= 2:
            start_p = float(s.iloc[0])
            end_p = float(s.iloc[-1])
            diff = end_p - start_p
            pct = (diff / start_p) * 100.0 if start_p else 0.0
            row = {name_col: col}
            if extra_map is not None:
                row["Tickers"] = extra_map.get(col, "")
            row.update(
                {
                    "Start": round(start_p, 2),
                    "Latest": round(end_p, 2),
                    "Change": round(diff, 2),
                    "Change (%)": round(pct, 2),
                    "Period Low": round(float(s.min()), 2),
                    "Period High": round(float(s.max()), 2),
                }
            )
            rows.append(row)
    return rows


st.set_page_config(
    page_title="Watchlist & Sector Share Price Timeline",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    div[data-testid="stMultiSelect"] [data-baseweb="select"] > div:first-child {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 0.25rem !important;
        height: auto !important;
        min-height: 2.75rem !important;
        max-height: none !important;
        overflow-y: visible !important;
        overflow-x: visible !important;
    }
    div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
        max-width: none !important;
        flex-shrink: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 Watchlist & Sector Share Price Timeline")

if "watchlists" not in st.session_state:
    st.session_state.watchlists = load_watchlists()
if "sector_overrides" not in st.session_state:
    st.session_state.sector_overrides = load_sector_overrides()

wl_names = list(st.session_state.watchlists.keys())
if (
    "active_watchlist" not in st.session_state
    or st.session_state.active_watchlist not in wl_names
):
    st.session_state.active_watchlist = wl_names[0]

# --- WATCHLIST SELECTION & MANAGEMENT ---
col_w1, col_w3 = st.columns([1.5, 1.5])
with col_w1:
    selected_wl = st.selectbox(
        "Watchlist",
        options=wl_names,
        index=wl_names.index(st.session_state.active_watchlist),
    )
    st.session_state.active_watchlist = selected_wl

with col_w3:
    extra_raw = st.text_input(
        "Temporary Compare Tickers (optional)",
        value="",
        placeholder="e.g., NVDA, AZN.L",
    )

wl_tickers = st.session_state.watchlists.get(selected_wl, [])
selected_tickers = st.multiselect(
    f"Shares in '{selected_wl}' ({len(wl_tickers)} in watchlist)",
    options=wl_tickers,
    default=wl_tickers,
    key=f"wl_multiselect_{selected_wl}",
)

with st.expander(
    "🗂️ Manage Watchlists, Add/Remove Tickers & Import/Export", expanded=False
):
    m_col1, m_col2, m_col3 = st.columns(3)

    with m_col1:
        st.markdown("**Watchlists**")
        new_wl_name = st.text_input(
            "New Watchlist Name", placeholder="e.g., UK Income"
        )
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
                st.session_state.active_watchlist = list(
                    st.session_state.watchlists.keys()
                )[0]
                save_watchlists(st.session_state.watchlists)
                st.rerun()

        st.markdown("**Quick Index Loaders**")
        idx_target = st.radio(
            "Load Index Into",
            options=["Dedicated index watchlist", "Active watchlist"],
            horizontal=True,
        )
        if st.button("Load FTSE 100"):
            dest_wl = (
                "FTSE 100" if idx_target == "Dedicated index watchlist" else selected_wl
            )
            added, dupes = apply_tickers_to_watchlist(
                dest_wl, get_live_ftse100_tickers(), mode="merge"
            )
            st.session_state.active_watchlist = dest_wl
            st.toast(
                f"Loaded {added} FTSE 100 ticker(s) into '{dest_wl}' ({dupes} duplicate(s) ignored)."
            )
            st.rerun()

        if st.button("Load S&P 500"):
            dest_wl = (
                "S&P 500" if idx_target == "Dedicated index watchlist" else selected_wl
            )
            added, dupes = apply_tickers_to_watchlist(
                dest_wl, get_live_sp500_tickers(), mode="merge"
            )
            st.session_state.active_watchlist = dest_wl
            st.toast(
                f"Loaded {added} S&P 500 ticker(s) into '{dest_wl}' ({dupes} duplicate(s) ignored)."
            )
            st.rerun()

    with m_col2:
        st.markdown(f"**Edit '{selected_wl}' Tickers**")
        add_ticker_raw = st.text_input(
            "Add Ticker(s)", placeholder="e.g., VOD.L or AAPL, MSFT"
        )
        if st.button("Add Ticker(s)"):
            to_add = [
                t.strip().upper()
                for t in add_ticker_raw.replace("\n", ",").split(",")
                if t.strip()
            ]
            if to_add:
                added, dupes = apply_tickers_to_watchlist(
                    selected_wl, to_add, mode="merge"
                )
                st.toast(
                    f"Added {added} ticker(s) to '{selected_wl}' ({dupes} duplicate(s) ignored)."
                )
                st.rerun()

        if wl_tickers:
            tickers_to_remove = st.multiselect(
                "Remove Ticker(s)", options=wl_tickers, default=[]
            )
            if st.button("Remove Selected Ticker(s)") and tickers_to_remove:
                remaining = [
                    t
                    for t in st.session_state.watchlists[selected_wl]
                    if t not in tickers_to_remove
                ]
                st.session_state.watchlists[selected_wl] = remaining
                save_watchlists(st.session_state.watchlists)
                st.rerun()

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
                raw_candidates = extract_raw_imported_tokens(
                    uploaded_wl_file, pasted_wl_tickers
                )
                deduped_import = normalize_ticker_list(raw_candidates)

                if not deduped_import:
                    st.warning("No valid tickers found to import.")
                elif import_mode == "Create new watchlist":
                    wl_target = target_import_wl.strip() or (
                        uploaded_wl_file.name.rsplit(".", 1)[0]
                        if uploaded_wl_file
                        else "Imported Watchlist"
                    )
                    added, skipped_dupes = apply_tickers_to_watchlist(
                        wl_target, raw_candidates, mode="merge"
                    )
                    st.session_state.active_watchlist = wl_target
                    st.toast(
                        f"Added {added} ticker(s) to '{wl_target}' ({skipped_dupes} duplicate(s) ignored)."
                    )
                    st.rerun()
                elif import_mode == "Replace active":
                    added, batch_dupes = apply_tickers_to_watchlist(
                        selected_wl, raw_candidates, mode="replace"
                    )
                    st.toast(
                        f"Replaced '{selected_wl}' with {added} unique ticker(s) ({batch_dupes} duplicate(s) ignored)."
                    )
                    st.rerun()
                else:
                    added, skipped_dupes = apply_tickers_to_watchlist(
                        selected_wl, raw_candidates, mode="merge"
                    )
                    st.toast(
                        f"Imported {added} new ticker(s) into '{selected_wl}' ({skipped_dupes} duplicate(s) ignored)."
                    )
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not import tickers: {exc}")

        slug_name = selected_wl.lower().replace(" ", "_")
        csv_export = (
            pd.DataFrame({"Ticker": wl_tickers}).to_csv(index=False).encode("utf-8")
        )
        json_export = json.dumps({selected_wl: wl_tickers}, indent=4).encode(
            "utf-8"
        )

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
        start_dt = st.date_input(
            "Start Date", value=today - timedelta(days=180)
        )
    with c_e:
        end_dt = st.date_input("End Date", value=today)

tab_shares, tab_sectors, tab_ftse_sectors, tab_sp500_sectors = st.tabs(
    [
        "📈 Share Price Timeline",
        "🏢 Watchlist Sector Timeline",
        "🇬🇧 FTSE 100 Sector Timeline",
        "🇺🇸 S&P 500 Sector Timeline",
    ]
)

# --- TAB 1: INDIVIDUAL SHARE TIMELINE ---
with tab_shares:
    if not tickers:
        st.info("Select at least one share from your watchlist or enter a ticker.")
    else:
        prices = fetch_timeline_prices(tickers, selected_tf, start_dt, end_dt)
        if prices.empty:
            st.warning("No price data available for the selected tickers or timeline.")
        else:
            share_y_label = (
                "Return (%)"
                if scale_mode == "Normalized (% Change)"
                else "Price (USD / GBP)"
            )
            share_fig = build_line_figure(
                prices, scale_mode, share_y_label, entity_label="Share"
            )
            st.plotly_chart(share_fig, use_container_width=True)

            st.subheader("Share Period Performance Summary")
            share_rows = build_summary_rows(prices, "Ticker")
            if share_rows:
                st.dataframe(
                    pd.DataFrame(share_rows), use_container_width=True, hide_index=True
                )

# --- TAB 2: WATCHLIST SECTOR AVERAGE TIMELINE ---
with tab_sectors:
    st.subheader("Watchlist Sector Average Timeline")
    if not tickers:
        st.info("Select at least one share from your watchlist or enter a ticker.")
    else:
        prices = fetch_timeline_prices(tickers, selected_tf, start_dt, end_dt)
        if prices.empty:
            st.warning("No price data available for the selected tickers or timeline.")
        else:
            allow_live = len(prices.columns) <= 30
            ticker_to_sector = {
                str(col).strip().upper(): resolve_ticker_sector(
                    str(col).strip().upper(),
                    st.session_state.sector_overrides,
                    allow_live_lookup=allow_live,
                )
                for col in prices.columns
            }

            with st.expander("Adjust Sector Assignments (optional)", expanded=False):
                mapping_df = pd.DataFrame(
                    [
                        {"Ticker": sym, "Sector": sec}
                        for sym, sec in ticker_to_sector.items()
                    ]
                )
                edited_df = st.data_editor(
                    mapping_df,
                    use_container_width=True,
                    hide_index=True,
                    disabled=["Ticker"],
                    key="sector_mapping_editor",
                )
                if st.button("Apply & Save Sector Assignments"):
                    for _, r in edited_df.iterrows():
                        t_sym = str(r["Ticker"]).strip().upper()
                        sec_val = str(r["Sector"]).strip() or "Unclassified"
                        st.session_state.sector_overrides[t_sym] = sec_val
                    save_sector_overrides(st.session_state.sector_overrides)
                    st.rerun()

            sector_df, sector_ticker_labels = build_sector_averages_df(
                prices, ticker_to_sector
            )
            available_sectors = list(sector_df.columns)
            selected_sectors = st.multiselect(
                "Sectors to Plot",
                options=available_sectors,
                default=available_sectors,
                key="wl_sectors_multiselect",
            )

            if not selected_sectors:
                st.info("Select at least one sector to display the sector timeline.")
            else:
                filtered_sector_df = sector_df[selected_sectors]
                sector_y_label = (
                    "Average Return (%)"
                    if scale_mode == "Normalized (% Change)"
                    else "Average Share Value"
                )
                sector_fig = build_line_figure(
                    filtered_sector_df,
                    scale_mode,
                    sector_y_label,
                    entity_label="Sector",
                )
                st.plotly_chart(sector_fig, use_container_width=True)

                st.subheader("Sector Period Performance Summary")
                sector_rows = build_summary_rows(
                    filtered_sector_df, "Sector", extra_map=sector_ticker_labels
                )
                if sector_rows:
                    st.dataframe(
                        pd.DataFrame(sector_rows),
                        use_container_width=True,
                        hide_index=True,
                    )

# --- TAB 3: FTSE 100 SECTOR AVERAGE TIMELINE ---
with tab_ftse_sectors:
    st.subheader("🇬🇧 FTSE 100 Sector Average Timeline")
    st.caption(
        "Averages all constituents within each FTSE 100 sector across the selected timeline (UK .L prices converted from pence to £)."
    )

    ftse_tickers = get_live_ftse100_tickers()
    ftse_prices = fetch_timeline_prices(ftse_tickers, selected_tf, start_dt, end_dt)

    if ftse_prices.empty:
        st.warning("Could not load FTSE 100 price history for this timeline.")
    else:
        ftse_sector_map = {
            str(col).strip().upper(): resolve_ticker_sector(
                str(col).strip().upper(),
                st.session_state.sector_overrides,
                allow_live_lookup=False,
            )
            for col in ftse_prices.columns
        }
        ftse_sector_df, ftse_sector_labels = build_sector_averages_df(
            ftse_prices, ftse_sector_map
        )

        ftse_sector_options = list(ftse_sector_df.columns)
        selected_ftse_sectors = st.multiselect(
            "FTSE 100 Sectors to Plot",
            options=ftse_sector_options,
            default=ftse_sector_options,
            key="ftse_sectors_multiselect",
        )

        if not selected_ftse_sectors:
            st.info("Select at least one FTSE 100 sector to plot.")
        else:
            filtered_ftse_df = ftse_sector_df[selected_ftse_sectors]
            ftse_y_label = (
                "Average Return (%)"
                if scale_mode == "Normalized (% Change)"
                else "Average Share Price (£)"
            )
            ftse_fig = build_line_figure(
                filtered_ftse_df,
                scale_mode,
                ftse_y_label,
                entity_label="FTSE 100 Sector",
            )
            st.plotly_chart(ftse_fig, use_container_width=True)

            st.subheader("FTSE 100 Sector Period Performance Summary")
            ftse_rows = build_summary_rows(
                filtered_ftse_df, "Sector", extra_map=ftse_sector_labels
            )
            if ftse_rows:
                st.dataframe(
                    pd.DataFrame(ftse_rows),
                    use_container_width=True,
                    hide_index=True,
                )

# --- TAB 4: S&P 500 SECTOR AVERAGE TIMELINE ---
with tab_sp500_sectors:
    st.subheader("🇺🇸 S&P 500 Sector Average Timeline")
    st.caption(
        "Averages all constituents within each S&P 500 sector across the selected timeline."
    )

    sp500_tickers = get_live_sp500_tickers()
    sp500_prices = fetch_timeline_prices(sp500_tickers, selected_tf, start_dt, end_dt)

    if sp500_prices.empty:
        st.warning("Could not load S&P 500 price history for this timeline.")
    else:
        sp500_sector_map = {
            str(col).strip().upper(): resolve_ticker_sector(
                str(col).strip().upper(),
                st.session_state.sector_overrides,
                allow_live_lookup=False,
            )
            for col in sp500_prices.columns
        }
        sp500_sector_df, sp500_sector_labels = build_sector_averages_df(
            sp500_prices, sp500_sector_map
        )

        sp500_sector_options = list(sp500_sector_df.columns)
        selected_sp500_sectors = st.multiselect(
            "S&P 500 Sectors to Plot",
            options=sp500_sector_options,
            default=sp500_sector_options,
            key="sp500_sectors_multiselect",
        )

        if not selected_sp500_sectors:
            st.info("Select at least one S&P 500 sector to plot.")
        else:
            filtered_sp500_df = sp500_sector_df[selected_sp500_sectors]
            sp500_y_label = (
                "Average Return (%)"
                if scale_mode == "Normalized (% Change)"
                else "Average Share Price ($)"
            )
            sp500_fig = build_line_figure(
                filtered_sp500_df,
                scale_mode,
                sp500_y_label,
                entity_label="S&P 500 Sector",
            )
            st.plotly_chart(sp500_fig, use_container_width=True)

            st.subheader("S&P 500 Sector Period Performance Summary")
            sp500_rows = build_summary_rows(
                filtered_sp500_df, "Sector", extra_map=sp500_sector_labels
            )
            if sp500_rows:
                st.dataframe(
                    pd.DataFrame(sp500_rows),
                    use_container_width=True,
                    hide_index=True,
                )
