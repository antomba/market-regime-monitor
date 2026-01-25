import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from fredapi import Fred
import json
import os

FRED_API_KEY = "PUT_YOUR_FRED_KEY_HERE"

fred = Fred(api_key=FRED_API_KEY)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------
# 1. DOWNLOAD DATA
# -----------------------
tickers = {
    "VIX": "^VIX",
    "VXST": "^VXST",
    "VXV": "^VXV",
    "VXMT": "^VXMT",
    "SPX": "^GSPC",
    "HYG": "HYG",
    "JNK": "JNK"
}

prices = yf.download(list(tickers.values()), period="6mo")["Adj Close"]
prices.columns = tickers.keys()

latest = prices.iloc[-1]

# -----------------------
# 2. MULTI-VIX SIGNAL
# -----------------------
def multi_vix_signal(row):
    if row["VXST"] < row["VIX"] < row["VXV"] < row["VXMT"]:
        return "bullish"
    if row["VXST"] > row["VIX"] > row["VXV"] > row["VXMT"]:
        return "bearish"
    return "neutral"

multi_vix = multi_vix_signal(latest)

# -----------------------
# 3. CREDIT SIGNAL
# -----------------------
def trend_signal(series):
    ema_fast = series.ewm(span=20).mean().iloc[-1]
    ema_slow = series.ewm(span=50).mean().iloc[-1]
    return "bullish" if ema_fast > ema_slow else "bearish"

credit_ratio = prices["HYG"] / prices["JNK"]
credit_signal = trend_signal(credit_ratio)

# -----------------------
# 4. NHNL (BREADTH PROXY)
# -----------------------
spx = prices["SPX"]
ema50 = spx.ewm(span=50).mean()
ema200 = spx.ewm(span=200).mean()
nhnl_signal = "bullish" if ema50.iloc[-1] > ema200.iloc[-1] else "bearish"

# -----------------------
# 5. SPX vs CREDIT
# -----------------------
spx_vs_credit = (
    "overperforms"
    if trend_signal(spx / credit_ratio) == "bullish"
    else "underperforms"
)

# -----------------------
# 6. SPX LONG TERM
# -----------------------
spx_long_term = "bullish" if ema50.iloc[-1] > ema200.iloc[-1] else "bearish"

# -----------------------
# 7. YIELD CURVE
# -----------------------
y10 = fred.get_series("DGS10").iloc[-1]
y2 = fred.get_series("DGS2").iloc[-1]
yield_curve = "normal" if (y10 - y2) > 0 else "inverted"

# -----------------------
# 8. REGIME SCORE
# -----------------------
score = 0
score += 1 if multi_vix == "bullish" else 0
score += 1 if credit_signal == "bullish" else 0
score += 1 if nhnl_signal == "bullish" else 0
score += 1 if spx_vs_credit == "overperforms" else 0
score += 1 if spx_long_term == "bullish" else 0
score -= 1 if yield_curve == "inverted" else 0

if score >= 3:
    regime = "risk-on"
elif score <= 0:
    regime = "risk-off"
else:
    regime = "neutral"

# -----------------------
# 9. OUTPUT
# -----------------------
output = {
    "date": datetime.utcnow().strftime("%Y-%m-%d"),
    "values": latest.round(2).to_dict(),
    "signals": {
        "multi_vix": multi_vix,
        "credit": credit_signal,
        "nhnl": nhnl_signal,
        "spx_vs_credit": spx_vs_credit,
        "spx_long_term": spx_long_term,
        "yield_curve": yield_curve,
    },
    "score": score,
    "regime": regime,
}

with open(f"{DATA_DIR}/latest.json", "w") as f:
    json.dump(output, f, indent=2)

print("DONE:", output)