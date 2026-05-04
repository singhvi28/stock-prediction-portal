import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
load_dotenv()

# =========================
# Technical Indicators
# =========================

def calculate_rsi(series, window=14):
    """Calculate Relative Strength Index (RSI)"""
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = -delta.clip(upper=0).rolling(window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(series, fast=12, slow=26, signal=9):
    """Calculate MACD, Signal Line, and Histogram"""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line, macd - signal_line


def calculate_bollinger(series, window=20, std=2):
    """Calculate Bollinger Bands (Upper, Lower, Middle)"""
    sma = series.rolling(window).mean()
    stddev = series.rolling(window).std()
    return sma + std * stddev, sma - std * stddev, sma


def prepare_sequences(data, features, lookback=60):
    """Prepare sequences for LSTM/Transformer input"""
    X, y = [], []

    try:
        close_idx = features.index("Close")
    except ValueError as exc:
        raise ValueError("Features list must contain 'Close'") from exc

    for i in range(lookback, len(data)):
        X.append(data[i - lookback : i])
        y.append(data[i, close_idx])

    return np.array(X), np.array(y)


def _fetch_marketstack_page(api_key, ticker, offset=0, limit=1000):
    """
    Fetch one page of daily EOD data from Marketstack v2.
    """
    url = "https://api.marketstack.com/v2/eod"
    params = {
        "access_key": api_key,
        "symbols": ticker,
        "limit": limit,
        "offset": offset,
        "sort": "ASC",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if "error" in payload:
        err = payload["error"]
        code = err.get("code", "marketstack_error")
        message = err.get("message", "Unknown Marketstack error")
        context = err.get("context")
        if context:
            raise Exception(f"Marketstack error ({code}): {message} | {context}")
        raise Exception(f"Marketstack error ({code}): {message}")

    rows = payload.get("data", [])
    return rows


def fetch_stock_data(ticker):
    """Fetch 10 years of stock data from Marketstack using MARKETSTACK_API_KEY from .env"""
    api_key = os.getenv("MARKETSTACK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "MARKETSTACK_API_KEY is missing. Add it to your .env file or environment."
        )

    all_rows = []
    offset = 0
    page_size = 1000

    while True:
        rows = _fetch_marketstack_page(api_key, ticker, offset=offset, limit=page_size)
        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < page_size:
            break

        offset += page_size

    if not all_rows:
        raise Exception(f"No data returned for ticker: {ticker}")

    df = pd.DataFrame(all_rows)

    # Normalise Marketstack's response to the same schema the rest of the app expects.
    required_map = {
        "date": "Date",
        "adj_open": "Open",
        "adj_high": "High",
        "adj_low": "Low",
        "adj_close": "Close",
        "adj_volume": "Volume",
    }

    missing = [src for src in required_map if src not in df.columns]
    if missing:
        raise Exception(f"Marketstack response missing required fields: {missing}")

    df = df.rename(columns=required_map)

    df["Date"] = pd.to_datetime(df["Date"], utc=True, errors="coerce").dt.tz_localize(None)

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Date", "Open", "High", "Low", "Close", "Volume"])
    df = df.sort_values("Date")

    ten_years_ago = datetime.now() - timedelta(days=10 * 365)
    df = df[df["Date"] >= ten_years_ago].reset_index(drop=True)

    return df[["Date", "Open", "High", "Low", "Close", "Volume"]]