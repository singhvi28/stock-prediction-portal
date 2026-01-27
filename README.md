# Stock Prediction & Forecast System

This project is a full-stack financial application that leverages deep learning to predict and forecast stock prices. It features a **PyTorch-based LSTM with Attention** backend, a **FastAPI** web server with JWT authentication, and a **Streamlit** dashboard for interactive visualization.

---

## Model Architecture

The core of this system is a **Multivariate LSTM (Long Short-Term Memory)** network enhanced by a **Bahdanau-style Attention Mechanism**. This architecture is specifically designed to handle the temporal dependencies and noise inherent in financial time-series data.

### 1. Feature Engineering (Multivariate Input)

The model does not rely on price alone. It processes a 18-dimensional feature vector for every time step, including:

* **OHLCV Data**: Open, High, Low, Close, and Volume.
* **Trend Indicators**: Moving Averages (50, 100, and 200-day).
* **Momentum Indicators**: Relative Strength Index (RSI) and MACD (Moving Average Convergence Divergence).
* **Volatility Indicators**: Bollinger Bands (Upper, Lower, Middle) and Price Range.
* **Volume Metrics**: 20-day Volume Moving Average.

### 2. Deep Learning Pipeline

* **Input Layer**: Accepts a sequence of the last 60 days of the 18-dimensional feature vectors.
* **Stacked LSTM Layers**: Two LSTM layers (128 units followed by 64 units) capture complex temporal patterns across different time scales.
* **Dropout Regularization**: Dropout layers (p=0.2) are applied between LSTMs to prevent overfitting to historical noise.
* **Attention Layer**:
* Computes a score for every time step in the lookback window using a Tanh activation and learnable weights.
* Applies a Softmax function to generate "Attention Weights," allowing the model to focus on the most relevant historical days (e.g., a recent price surge) while ignoring irrelevant ones.
* Produces a **Context Vector** as a weighted sum of the LSTM outputs.


* **Output Dense Layers**: Two fully connected layers (32 units and 1 unit) map the context vector to a single predicted Close price.

### 3. Recursive 30-Day Forecasting

Unlike simple one-step predictions, the system performs a **30-day recursive forecast**. The model predicts the price for , then appends this prediction back into the input sequence to predict , repeating this process for a full month.

---

## Tech Stack

* **Deep Learning**: PyTorch.
* **Data Processing**: NumPy, Pandas, Scikit-Learn (MinMaxScaler).
* **Backend**: FastAPI, Uvicorn, PyJWT (Authentication), Bcrypt (Password Hashing).
* **Frontend**: Streamlit.
* **Data Source**: Stooq (via pandas-datareader).

---

## Setup & Installation

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd stock-pred

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

```

### 2. Start the Backend API

```bash
cd api
python main.py

```

*The API server starts at `http://localhost:8000`. You can view the automated Swagger documentation at `/docs`.*

### 3. Start the Streamlit Dashboard

Open a new terminal and run:

```bash
cd frontend
streamlit run app.py

```

---

## 🔐 Authentication & Usage

The system uses **JWT (JSON Web Tokens)** for secure access to the prediction endpoints.

**Demo Credentials:**

* **Username**: `demo`
* **Password**: `demo123`

### Features:

* **Backtest Metrics**: View RMSE, MAE, and Directional Accuracy based on historical performance.
* **Visualizations**: High-quality dark-mode plots showing actual prices vs. model backtests vs. future forecasts.
* **Forecast Table**: A data table highlighting the predicted prices for the next 30 days.
