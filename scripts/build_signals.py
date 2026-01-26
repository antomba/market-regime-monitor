import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, UTC
from fredapi import Fred
import json
import os

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

ema20 = credit_ratio.ewm(span=20).mean()
ema50 = credit_ratio.ewm(span=50).mean()
credit_signal = "bullish" if ema20.iloc[-1] > ema50.iloc[-1] else "bearish"

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

# ---------- 9. REGIME SCORE ----------
score = 0
score += multi_vix == "bullish"
score += credit_signal == "bullish"
score += nhnl_signal == "bullish"
score += spx_vs_credit == "overperforms"
score += spx_long_term == "bullish"
score -= yield_curve == "inverted"

if score >= 3:
    regime = "risk-on"
elif score <= 0:
    regime = "risk-off"
else:
    regime = "neutral"

# ---------- 10. OUTPUT ----------
date_str = datetime.now(UTC).strftime("%Y-%m-%d")
output = {
    "date": date_str,
    "values": {k: (round(v, 2) if v is not None else None) for k, v in latest.items()},
    "signals": {
        "multi_vix": multi_vix,
        "credit": credit_signal,
        "nhnl": nhnl_signal,
        "spx_vs_credit": spx_vs_credit,
        "spx_long_term": spx_long_term,
        "yield_curve": yield_curve,
    },
    "score": int(score),
    "regime": regime,
}

for data_dir in DATA_DIRS:
    with open(f"{data_dir}/latest.json", "w") as f:
        json.dump(output, f, indent=2)
    history_path = os.path.join(data_dir, "history", f"{date_str}.json")
    with open(history_path, "w") as f:
        json.dump(output, f, indent=2)
    index_path = os.path.join(data_dir, "history", "index.json")
    if os.path.exists(index_path):
        try:
            with open(index_path, "r") as f:
                index = json.load(f)
        except json.JSONDecodeError:
            index = []
    else:
        index = []
    if date_str not in index:
        index.append(date_str)
    index = sorted(index)
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
