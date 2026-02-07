import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import pandas_datareader.data as web
import warnings

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
    return sma + std*stddev, sma - std*stddev, sma

def prepare_sequences(data, features, lookback=60):
    """Prepare sequences for LSTM/Transformer input"""
    X, y = [], []
    # Identify close_idx assuming 'Close' is in features list
    # If features is just a list of strings, we find the index of 'Close'
    # But wait, 'data' is a numpy array (scaled). 
    # 'features' argument in original code was the list of column names.
    # We need to find the index of 'Close' within that list to set 'y'.
    try:
        close_idx = features.index('Close')
    except ValueError:
        # Fallback or error if Close is not present
        raise ValueError("Features list must contain 'Close'")
        
    for i in range(lookback, len(data)):
        X.append(data[i-lookback:i])
        y.append(data[i, close_idx])
    return np.array(X), np.array(y)

def fetch_stock_data_stooq(ticker):
    """Fetch 10 years of stock data from Stooq"""
    df = web.DataReader(ticker, 'stooq')
    if df.empty: 
        raise Exception("No data from Stooq")
    df = df.reset_index().rename(columns={
        'Date': 'Date', 
        'Open': 'Open', 
        'High': 'High', 
        'Low': 'Low', 
        'Close': 'Close', 
        'Volume': 'Volume'
    })
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    ten_years_ago = datetime.now() - timedelta(days=10*365)
    return df[df['Date'] >= ten_years_ago].reset_index(drop=True)
