import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, UTC
from fredapi import Fred
import json
import os
import sqlite3

# ---------- CONFIG ----------
FRED_API_KEY = os.getenv("FRED_API_KEY")
DATA_DIRS = ["data", "docs/data"]
for data_dir in DATA_DIRS:
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, "history"), exist_ok=True)

fred = Fred(api_key=FRED_API_KEY)


# ---------- SAFE DOWNLOAD ----------
def safe_download(ticker, period="6mo"):
    df = yf.download(ticker, period=period, progress=False)

    if df is None or df.empty:
        return None

    def as_series(value):
        if isinstance(value, pd.Series):
            return value
        if isinstance(value, pd.DataFrame):
            if value.shape[1] == 0:
                return None
            return value.iloc[:, 0]
        return value

    # Case 1: standard columns
    if "Adj Close" in df.columns:
        return as_series(df["Adj Close"])

    if "Close" in df.columns:
        return as_series(df["Close"])

    # Case 2: MultiIndex columns (common in GitHub Actions)
    if isinstance(df.columns, pd.MultiIndex):
        for col in ["Adj Close", "Close"]:
            try:
                return as_series(df.xs(col, level=0, axis=1))
            except KeyError:
                continue

    return None


# ---------- 1. CORE ASSETS ----------
data = {}

data["VIX"] = safe_download("^VIX")
data["SPX"] = safe_download("^GSPC")
data["HYG"] = safe_download("HYG")
data["JNK"] = safe_download("JNK")

# ---------- 2. VIX TERM STRUCTURE ----------

vix = data["VIX"]

if vix is None:
    raise Exception("VIX not available – cannot proceed")


def download_first_available(candidates, periods=("5d", "1mo", "3mo", "6mo")):
    """Try a list of Yahoo tickers and periods and return the first non-empty Series."""
    for period in periods:
        for t in candidates:
            s = safe_download(t, period=period)
            if s is not None and not s.empty:
                return s
    return None


# Yahoo Finance has historically used different tickers for these Cboe indices.
# Prefer the currently common tickers, but fall back to the older ones.
VXST = download_first_available(["^VIX9D", "^VXST"])  # 9-day VIX
VXV = download_first_available(["^VIX3M", "^VXV"])  # 3-month VIX
VXMT = download_first_available(["^VIX6M", "^VXMT"])  # 6-month VIX

if VXST is None or VXV is None or VXMT is None:
    # Do not hard-fail; proceed with a neutral multi-vix signal.
    print(
        "Warning: VIX term structure not fully available; "
        "multi_vix signal will be set to 'neutral'."
    )


# ---------- 3. MULTI-VIX SIGNAL ----------
def last_value(x):
    if x is None:
        return None
    if isinstance(x, pd.Series):
        return float(x.dropna().iloc[-1])
    if isinstance(x, pd.DataFrame):
        if x.shape[1] == 0:
            raise ValueError("Empty DataFrame passed to last_value")
        return float(x.iloc[:, 0].dropna().iloc[-1])
    return float(x)


latest = {
    "VXST": last_value(VXST),
    "VIX": last_value(vix),
    "VXV": last_value(VXV),
    "VXMT": last_value(VXMT),
    "HYG": last_value(data["HYG"]),
    "JNK": last_value(data["JNK"]),
}


def multi_vix_signal(v):
    # If we can't compute the full curve, fall back to missing data.
    if any(v.get(k) is None for k in ["VXST", "VIX", "VXV", "VXMT"]):
        return "missing data"

    if v["VXST"] < v["VIX"] < v["VXV"] < v["VXMT"]:
        return "bullish"
    if v["VXST"] > v["VIX"] > v["VXV"] > v["VXMT"]:
        return "bearish"
    return "neutral"


multi_vix = multi_vix_signal(latest)

# ---------- 4. CREDIT SIGNAL ----------
credit_ratio = data["HYG"] / data["JNK"]


# ---------- 4a. HYG/JNK TREND ----------
def trend_signal(series):
    ema20_s = series.ewm(span=20).mean().iloc[-1]
    ema50_s = series.ewm(span=50).mean().iloc[-1]
    if ema20_s > ema50_s:
        return "bullish"
    if ema20_s < ema50_s:
        return "bearish"
    return "neutral"


hyg_trend = trend_signal(data["HYG"])
jnk_trend = trend_signal(data["JNK"])

# ---------- 5. NHNL (BREADTH PROXY) ----------
spx = data["SPX"]
ema50_spx = spx.ewm(span=50).mean()
ema200_spx = spx.ewm(span=200).mean()
nhnl_signal = "bullish" if ema50_spx.iloc[-1] > ema200_spx.iloc[-1] else "bearish"

# ---------- 6. SPX vs CREDIT ----------
spx_vs_credit = (
    "overperforms"
    if (spx / credit_ratio).ewm(span=50).mean().iloc[-1]
    > (spx / credit_ratio).ewm(span=200).mean().iloc[-1]
    else "underperforms"
)

# ---------- 7. SPX LONG TERM ----------
spx_long_term = "bullish" if ema50_spx.iloc[-1] > ema200_spx.iloc[-1] else "bearish"

# ---------- 8. YIELD CURVE ----------
y10 = fred.get_series("DGS10").dropna().iloc[-1]
y2 = fred.get_series("DGS2").dropna().iloc[-1]
yield_curve = "normal" if (y10 - y2) > 0 else "inverted"

# ---------- 9. OUTPUT ----------
date_str = datetime.now(UTC).strftime("%Y-%m-%d")
output = {
    "date": date_str,
    "values": {k: (round(v, 2) if v is not None else None) for k, v in latest.items()},
    "signals": {
        "multi_vix": multi_vix,
        "hyg_trend": hyg_trend,
        "jnk_trend": jnk_trend,
        "nhnl": nhnl_signal,
        "spx_vs_credit": spx_vs_credit,
        "spx_long_term": spx_long_term,
        "yield_curve": yield_curve,
    },
}


def write_sqlite_snapshot(db_path, payload):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                date TEXT PRIMARY KEY,
                vxst REAL,
                vix REAL,
                vxv REAL,
                vxmt REAL,
                hyg REAL,
                jnk REAL,
                multi_vix TEXT,
                hyg_trend TEXT,
                jnk_trend TEXT,
                nhnl TEXT,
                spx_vs_credit TEXT,
                spx_long_term TEXT,
                yield_curve TEXT,
                values_json TEXT NOT NULL,
                signals_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO signals
                (
                    date, vxst, vix, vxv, vxmt, hyg, jnk,
                    multi_vix, hyg_trend, jnk_trend, nhnl, spx_vs_credit,
                    spx_long_term, yield_curve,
                    values_json, signals_json, payload_json, created_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["date"],
                payload["values"].get("VXST"),
                payload["values"].get("VIX"),
                payload["values"].get("VXV"),
                payload["values"].get("VXMT"),
                payload["values"].get("HYG"),
                payload["values"].get("JNK"),
                payload["signals"].get("multi_vix"),
                payload["signals"].get("hyg_trend"),
                payload["signals"].get("jnk_trend"),
                payload["signals"].get("nhnl"),
                payload["signals"].get("spx_vs_credit"),
                payload["signals"].get("spx_long_term"),
                payload["signals"].get("yield_curve"),
                json.dumps(payload["values"], separators=(",", ":")),
                json.dumps(payload["signals"], separators=(",", ":")),
                json.dumps(payload, separators=(",", ":")),
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


for data_dir in DATA_DIRS:
    with open(f"{data_dir}/latest.json", "w") as f:
        json.dump(output, f, indent=2)
    write_sqlite_snapshot(os.path.join(data_dir, "history.sqlite"), output)
