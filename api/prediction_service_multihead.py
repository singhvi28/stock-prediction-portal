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
# Multi-Head Attention & Model
# =========================

class PositionalEncoding(nn.Module):
    """Add positional information to input sequences"""
    def __init__(self, d_model, max_len=5000):
        super().__init__()
        
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)
    
    def forward(self, x):
        """
        Args:
            x: Tensor of shape (batch_size, seq_len, d_model)
        """
        return x + self.pe[:, :x.size(1), :]


class MultiHeadAttentionModel(nn.Module):
    """
    Stock prediction model using multi-head attention mechanism.
    Replaces LSTM layers with Transformer encoder layers.
    """
    def __init__(self, input_size, d_model=128, nhead=8, num_layers=2, dropout=0.2):
        super().__init__()
        
        self.d_model = d_model
        
        # Input projection layer to map features to d_model dimensions
        self.input_projection = nn.Linear(input_size, d_model)
        
        # Positional encoding
        self.pos_encoder = PositionalEncoding(d_model)
        
        # Multi-head attention layers via TransformerEncoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            activation='relu',
            batch_first=True,
            norm_first=False
        )
        
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers
        )
        
        # Attention pooling layer (alternative to just taking last output)
        self.attention_pool = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=nhead,
            dropout=dropout,
            batch_first=True
        )
        
        # Query for attention pooling
        self.query = nn.Parameter(torch.randn(1, 1, d_model))
        
        # Output layers
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(d_model, 32)
        self.fc2 = nn.Linear(32, 1)
    
    def forward(self, x):
        """
        Args:
            x: Input tensor of shape (batch_size, seq_len, input_size)
        Returns:
            Output predictions of shape (batch_size, 1)
        """
        batch_size = x.size(0)
        
        # Project input to d_model dimensions
        x = self.input_projection(x)  # (batch_size, seq_len, d_model)
        
        # Add positional encoding
        x = self.pos_encoder(x)
        
        # Apply transformer encoder with multi-head attention
        x = self.transformer_encoder(x)  # (batch_size, seq_len, d_model)
        
        # Use attention pooling to aggregate sequence information
        # Expand query to match batch size
        query = self.query.expand(batch_size, -1, -1)  # (batch_size, 1, d_model)
        context, _ = self.attention_pool(query, x, x)  # (batch_size, 1, d_model)
        context = context.squeeze(1)  # (batch_size, d_model)
        
        # Pass through output layers
        x = self.dropout(context)
        x = F.relu(self.fc1(x))
        return self.fc2(x)


# =========================
# Technical Indicators (Imported)
# =========================
from technical_indicators import (
    calculate_rsi, 
    calculate_macd, 
    calculate_bollinger, 
    prepare_sequences, 
    fetch_stock_data_stooq
)

# =========================
# Custom Loss Function
# =========================
class DirectionalMSELoss(nn.Module):
    def __init__(self, alpha=1.0):
        super().__init__()
        self.mse = nn.MSELoss()
        self.alpha = alpha

    def forward(self, pred, target, prev_price):
        # Standard regression loss
        mse_loss = self.mse(pred, target)
        
        # Calculate actual direction: 1 if price went up, -1 if down
        actual_move = torch.sign(target - prev_price)
        
        # Penalty is applied if (actual_move) and (pred - prev_price) have opposite signs
        # Using ReLU to ensure we only penalize incorrect directions
        penalty = torch.mean(torch.relu(-actual_move * (pred - prev_price)))
        
        return mse_loss + self.alpha * penalty

# =========================
# Main Prediction Function
# =========================

def get_stock_predictions(ticker, lookback=60, epochs=15, forecast_days=30):
    """
    Fetches data, trains a Multi-Head Attention model, 
    calculates performance metrics, and generates a 30-day recursive forecast.
    
    Args:
        ticker: Stock ticker symbol
        lookback: Number of time steps to look back
        epochs: Number of training epochs
        forecast_days: Number of days to forecast into the future
    
    Returns:
        Dictionary containing metrics, historical data, and forecasts
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
        'Open', 'High', 'Low', 'Close', 'Volume',
        'MA_50', 'MA_100', 'MA_200', 'RSI',
        'MACD', 'MACD_Signal', 'MACD_Hist',
        'BB_Upper', 'BB_Lower', 'BB_Middle',
        'Pct_Change', 'Volume_MA', 'Price_Range'
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

    # 3. Model Training with Multi-Head Attention
    model = MultiHeadAttentionModel(
        input_size=len(features),
        d_model=64,
        nhead=4,
        num_layers=2,
        dropout=0.2
    ).to(device)
    
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = DirectionalMSELoss(alpha=1.0)

    model.train()
    loader = DataLoader(TensorDataset(X_train_t, y_train_t), batch_size=32, shuffle=True)
    
    for epoch in range(epochs):
        epoch_loss = 0.0
        for x, y in loader:
            optimizer.zero_grad()
            output = model(x).squeeze()
            
            # NEW: Extract the 'Close' price from the very last day of the lookback window
            # x shape is (batch, lookback, features)
            prev_price = x[:, -1, close_idx] 
            
            # Updated loss call
            loss = criterion(output, y, prev_price)
            
            loss.backward()
        
            # Gradient clipping remains the same
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            
            optimizer.step()
            epoch_loss += loss.item()

        # Optional: Print training progress
        if (epoch + 1) % 5 == 0:
            avg_loss = epoch_loss / len(loader)
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.6f}")

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
    current_batch = scaled_data[-lookback:].copy()  # Start with the most recent window

    model.eval()
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

    future_inv = close_scaler.inverse_transform(
        np.array(future_preds_scaled).reshape(-1, 1)
    ).flatten()

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