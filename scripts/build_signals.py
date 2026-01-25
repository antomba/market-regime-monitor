import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from fredapi import Fred
import json
import os

# ---------- CONFIG ----------
FRED_API_KEY = os.getenv("FRED_API_KEY")
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

fred = Fred(api_key=FRED_API_KEY)

# ---------- SAFE DOWNLOAD ----------
def safe_download(ticker, period="6mo"):
    df = yf.download(ticker, period=period, progress=False)

    if df is None or df.empty:
        return None

    # Case 1: standard columns
    if "Adj Close" in df.columns:
        return df["Adj Close"]

    if "Close" in df.columns:
        return df["Close"]

    # Case 2: MultiIndex columns (common in GitHub Actions)
    if isinstance(df.columns, pd.MultiIndex):
        for col in ["Adj Close", "Close"]:
            try:
                return df.xs(col, level=0, axis=1)
            except KeyError:
                continue

    return None

# ---------- 1. CORE ASSETS ----------
data = {}

data["VIX"] = safe_download("^VIX")
data["SPX"] = safe_download("^GSPC")
data["HYG"] = safe_download("HYG")
data["JNK"] = safe_download("JNK")

# ---------- 2. VIX TERM STRUCTURE (WITH FALLBACK) ----------
# Yahoo часто ломается → используем proxy
# VXST ≈ VIX
# VXV ≈ VIX + 10%
# VXMT ≈ VIX + 20%

vix = data["VIX"]

if vix is None:
    raise Exception("VIX not available – cannot proceed")

VXST = safe_download("^VXST") or vix
VXV = safe_download("^VXV") or (vix * 1.10)
VXMT = safe_download("^VXMT") or (vix * 1.20)

# ---------- 3. MULTI-VIX SIGNAL ----------
latest = {
    "VXST": VXST.iloc[-1],
    "VIX": vix.iloc[-1],
    "VXV": VXV.iloc[-1],
    "VXMT": VXMT.iloc[-1],
}

def multi_vix_signal(v):
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
output = {
    "date": datetime.utcnow().strftime("%Y-%m-%d"),
    "values": {k: round(v, 2) for k, v in latest.items()},
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

with open(f"{DATA_DIR}/latest.json", "w") as f:
    json.dump(output, f, indent=2)

print("✅ Market regime built:", regime)