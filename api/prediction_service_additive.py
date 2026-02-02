import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import warnings


import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import TensorDataset, DataLoader

from sklearn.preprocessing import MinMaxScaler
import pandas_datareader.data as web

warnings.filterwarnings('ignore')

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# =========================
# Attention & Model
# =========================
class AttentionLayer(nn.Module):
    def __init__(self, hidden_size, attention_size=64):
        super().__init__()
        self.W = nn.Linear(hidden_size, attention_size)
        self.U = nn.Linear(attention_size, 1, bias=False)

    def forward(self, lstm_output):
        scores = torch.tanh(self.W(lstm_output))
        scores = self.U(scores).squeeze(-1)
        weights = F.softmax(scores, dim=1)
        context = torch.sum(lstm_output * weights.unsqueeze(-1), dim=1)
        return context, weights

class MultivariateLSTMWithAttention(nn.Module):
    def __init__(self, input_size, hidden_size1=128, hidden_size2=64, dropout=0.2):
        super().__init__()
        self.lstm1 = nn.LSTM(input_size, hidden_size1, batch_first=True)
        self.dropout1 = nn.Dropout(dropout)
        self.lstm2 = nn.LSTM(hidden_size1, hidden_size2, batch_first=True)
        self.dropout2 = nn.Dropout(dropout)
        self.attention = AttentionLayer(hidden_size2)
        self.fc1 = nn.Linear(hidden_size2, 32)
        self.fc2 = nn.Linear(32, 1)

    def forward(self, x):
        x, _ = self.lstm1(x)
        x = self.dropout1(x)
        x, _ = self.lstm2(x)
        x = self.dropout2(x)
        context, _ = self.attention(x)
        x = F.relu(self.fc1(context))
        return self.fc2(x)

# =========================
# Technical Indicators
# =========================
def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = -delta.clip(upper=0).rolling(window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line, macd - signal_line

def calculate_bollinger(series, window=20, std=2):
    sma = series.rolling(window).mean()
    stddev = series.rolling(window).std()
    return sma + std*stddev, sma - std*stddev, sma

def prepare_sequences(data, features, lookback=60):
    X, y = [], []
    close_idx = features.index('Close')
    for i in range(lookback, len(data)):
        X.append(data[i-lookback:i])
        y.append(data[i, close_idx])
    return np.array(X), np.array(y)

def fetch_stock_data_stooq(ticker):
    df = web.DataReader(ticker, 'stooq')
    if df.empty: raise Exception("No data from Stooq")
    df = df.reset_index().rename(columns={'Date': 'Date', 'Open': 'Open', 'High': 'High', 'Low': 'Low', 'Close': 'Close', 'Volume': 'Volume'})
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    ten_years_ago = datetime.now() - timedelta(days=10*365)
    return df[df['Date'] >= ten_years_ago].reset_index(drop=True)

# =========================
# Main Prediction Function
# =========================

def get_stock_predictions(ticker, lookback=60, epochs=15, forecast_days=30):
    """
    Fetches data, trains a Multivariate LSTM with Attention, 
    calculates performance metrics, and generates a 30-day recursive forecast.
    """
    # 1. Fetch and Prepare Data
    df = fetch_stock_data_stooq(ticker)
    
    # Calculate Indicators
    df['MA_50'] = df['Close'].rolling(50).mean()
    df['MA_100'] = df['Close'].rolling(100).mean()
    df['MA_200'] = df['Close'].rolling(200).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calculate_macd(df['Close'])
    df['BB_Upper'], df['BB_Lower'], df['BB_Middle'] = calculate_bollinger(df['Close'])
    df['Pct_Change'] = df['Close'].pct_change()
    df['Volume_MA'] = df['Volume'].rolling(20).mean()
    df['Price_Range'] = (df['High'] - df['Low']) / df['Close']
    
    df.dropna(inplace=True)

    features = [
        'Open','High','Low','Close','Volume',
        'MA_50','MA_100','MA_200','RSI',
        'MACD','MACD_Signal','MACD_Hist',
        'BB_Upper','BB_Lower','BB_Middle',
        'Pct_Change','Volume_MA','Price_Range'
    ]
    close_idx = features.index('Close')
    
    # 2. Scaling and Sequencing
    data_values = df[features].values
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(data_values)

    # Split for metric evaluation (80% train, 20% test)
    split = int(len(scaled_data) * 0.8)
    train_scaled = scaled_data[:split]
    
    X_train, y_train = prepare_sequences(train_scaled, features, lookback)
    X_full, y_full = prepare_sequences(scaled_data, features, lookback)

    X_train_t = torch.FloatTensor(X_train).to(device)
    y_train_t = torch.FloatTensor(y_train).to(device)

    # 3. Model Training
    model = MultivariateLSTMWithAttention(len(features)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()

    model.train()
    loader = DataLoader(TensorDataset(X_train_t, y_train_t), batch_size=32, shuffle=True)
    for _ in range(epochs):
        for x, y in loader:
            optimizer.zero_grad()
            output = model(x).squeeze()
            loss = criterion(output, y)
            loss.backward()
            optimizer.step()

    # 4. Evaluation Metrics (Backtest on the most recent data)
    model.eval()
    with torch.no_grad():
        # Predict on the full dataset to compare with actuals
        preds_scaled = model(torch.FloatTensor(X_full).to(device)).cpu().numpy().flatten()
    
    # We need a dedicated scaler for the Close price to inverse transform accurately
    close_scaler = MinMaxScaler()
    close_scaler.fit(data_values[:, close_idx].reshape(-1, 1))
    
    preds_inv = close_scaler.inverse_transform(preds_scaled.reshape(-1, 1)).flatten()
    actual_inv = close_scaler.inverse_transform(y_full.reshape(-1, 1)).flatten()

    # Calculate metrics on the 'test' portion of our sequences
    test_start_idx = split - lookback
    y_test_actual = actual_inv[test_start_idx:]
    y_test_preds = preds_inv[test_start_idx:]

    rmse = np.sqrt(np.mean((y_test_preds - y_test_actual)**2))
    mae = np.mean(np.abs(y_test_preds - y_test_actual))
    mape = np.mean(np.abs((y_test_actual - y_test_preds) / y_test_actual)) * 100

    # Directional Accuracy
    # Compare if prediction correctly identifies the move from Day N-1 to Day N
    y_actual_prev = actual_inv[test_start_idx-1 : -1]
    actual_direction = np.sign(y_test_actual - y_actual_prev)
    pred_direction = np.sign(y_test_preds - y_actual_prev)
    directional_accuracy = np.mean(actual_direction == pred_direction) * 100

    # 5. 30-Day Future Forecast (Recursive)
    future_preds_scaled = []
    current_batch = scaled_data[-lookback:].copy() # Start with the most recent window

    for _ in range(forecast_days):
        with torch.no_grad():
            input_tensor = torch.FloatTensor(current_batch).unsqueeze(0).to(device)
            pred_point = model(input_tensor).cpu().numpy().flatten()[0]
            future_preds_scaled.append(pred_point)
            
            # Create next input row: we update price-related features with the prediction
            new_row = current_batch[-1].copy()
            new_row[close_idx] = pred_point  # Update Close
            new_row[0:3] = pred_point        # Update Open/High/Low as a simple proxy
            
            # Shift window: remove first day, add the predicted day
            current_batch = np.append(current_batch[1:], [new_row], axis=0)

    future_inv = close_scaler.inverse_transform(np.array(future_preds_scaled).reshape(-1, 1)).flatten()

    # 6. Visualization Data Preparation
    dates = df['Date'].iloc[lookback:].reset_index(drop=True)
    last_date = dates.iloc[-1]
    
    # Create future date range
    future_dates = [last_date + timedelta(days=i+1) for i in range(forecast_days)]
    
    return {
        "ticker": ticker,
        "metrics": {
            "rmse": float(rmse),
            "mae": float(mae),
            "mape": float(mape),
            "directional_accuracy": float(directional_accuracy)
        },
        "last_price": float(actual_inv[-1]),
        "historical_dates": [d.strftime('%Y-%m-%d') for d in dates],
        "historical_prices": [float(x) for x in actual_inv],
        "model_historical_predictions": [float(x) for x in preds_inv],
        "forecast_dates": [d.strftime('%Y-%m-%d') for d in future_dates],
        "forecast_prices": [float(x) for x in future_inv]
    }
    