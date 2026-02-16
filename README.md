# Stock Prediction Portal

A full-stack machine learning application for predicting stock prices using advanced attention mechanisms. The system features a FastAPI backend with asynchronous task processing via Celery and RabbitMQ, a Streamlit frontend for user interaction, and comprehensive user management with Razorpay payment integration.

## 🏗️ Architecture Overview

The backend follows a distributed asynchronous architecture to manage diverse workloads:

* **API Server**: Built with **FastAPI** to handle RESTful requests and JWT-based authentication.
* **Task Queue**: Utilizes **Celery** with **RabbitMQ** as the message broker to decouple long-running ML tasks from the request-response cycle.
* **Distributed Workers**: Segregated into specialized queues for optimized resource management:
    * `worker-payments`: Optimized for high concurrency and low-latency transaction processing.
    * `worker-ml`: Strictly throttled to manage compute-heavy PyTorch model training and forecasting.
* **Storage Layer**: Uses **PostgreSQL** for persistent data, **Redis** for task result caching and idempotency locks, and **SQLAlchemy** for ORM management.

## 🚀 Features

-   **Stock Prediction**: Predict future stock prices for ANY ticker using:
    -   Multihead Attention Models
    -   Additive Attention Models
    -   Recursive 30-day forecasting based on 18 technical indicators including RSI, MACD, and Bollinger Bands.
-   **Interactive Dashboard**: Built with Streamlit for real-time visualization of historical data and forecast trends.
-   **User Authentication**: Secure JWT-based login, registration, and password reset flows.
-   **Credit System**: Pay-per-use model integrated with Razorpay. Buy credits to run premium predictions.
-   **Secure Financial Logic**:
    -   **Razorpay Integration**: End-to-end payment processing with webhook-driven credit fulfillment.
    -   **Transaction Integrity**: Utilizes **SQLAlchemy row-level locking** (`with_for_update`) to prevent double-spend race conditions.
    -   **Idempotency**: Redis-based locking to prevent duplicate transaction processing.
-   **Asynchronous Processing**: Heavy ML tasks are offloaded to Celery workers (RabbitMQ broker) to ensure a responsive UI.
-   **Scalable Architecture**: Microservices ready with Docker Compose.

## 🛠️ Tech Stack

-   **Frontend**: Streamlit, Plotly, Requests
-   **Backend**: FastAPI, SQLAlchemy, Pydantic
-   **ML/AI**: PyTorch, Scikit-Learn, Pandas, Numpy
-   **Task Queue**: Celery, RabbitMQ
-   **Caching**: Redis
-   **Database**: PostgreSQL
-   **Containerization**: Docker, Docker Compose

## 📂 Project Structure

```bash
.
├── api/                 # FastAPI backend and Celery workers
│   ├── main.py          # API entry point
│   ├── tasks.py         # Celery task definitions
│   ├── models.py        # Database models
│   └── ...
├── frontend/            # Streamlit dashboard
│   ├── app.py           # Frontend entry point
│   ├── views.py         # UI Pages (Auth, Dashboard)
│   └── ...
├── docker-compose.yml   # Orchestration for all services
├── requirements.txt     # Backend dependencies
└── README.md            # Project documentation
```

## 🗄️ Database Schema

The application uses **PostgreSQL** with **SQLAlchemy ORM**. Below is the schema design:

### 1. **Users** (`users`)
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Unique user ID |
| `email` | String | Unique email address |
| `password_hash` | String | Hashed password |
| `credits` | Integer | Current credit balance (Default: 5) |
| `created_at` | DateTime | Account creation timestamp |

### 2. **Prediction History** (`prediction_history`)
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Unique record ID |
| `user_id` | Integer (FK) | Reference to `users.id` |
| `task_id` | String | Celery task ID |
| `ticker` | String | Stock ticker symbol (e.g., AAPL) |
| `model_type` | String | Model used (additive/multihead) |
| `directional_accuracy` | Float | Model accuracy metric |
| `prediction_data` | JSONB | Raw prediction results & metrics |
| `created_at` | DateTime | Timestamp of request |

### 3. **Transactions** (`transactions`)
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Unique transaction ID |
| `user_id` | Integer (FK) | Reference to `users.id` |
| `razorpay_order_id` | String | Order ID from Razorpay |
| `razorpay_payment_id` | String | Payment ID (updated on success) |
| `amount_paise` | Integer | Amount in paise |
| `credits` | Integer | Credits purchased |
| `status` | String | `PENDING`, `SUCCESS`, `FAILED` |

### 4. **Credit Ledger** (`credit_ledger`)
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Unique ledger ID |
| `user_id` | Integer (FK) | Reference to `users.id` |
| `transaction_id` | Integer (FK) | Linked transaction (nullable) |
| `amount` | Integer | Credits added/deducted |
| `reason` | String | `PURCHASE`, `REFUND_FAILED_TASK`, etc. |

## ⚡ Setup & Installation

### Docker Setup (Recommended)

**Prerequisites**: [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/).

1. **Clone the repository**:
   ```bash
   git clone https://github.com/singhvi28/stock-pred.git
   cd stock-pred
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the `api/` directory:
   ```ini
   # Database
   DATABASE_URL=postgresql+asyncpg://user:password@db:5432/stock_db

   # Security
   SECRET_KEY=your_super_secret_key
   ALGORITHM=HS256

   # Payments (Razorpay)
   RAZORPAY_KEY_ID=your_razorpay_key_id
   RAZORPAY_KEY_SECRET=your_razorpay_key_secret

   # Celery / Broker
   RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672//
   REDIS_URL=redis://redis:6379/0
   ```
   > **Note**: You essentially need to provide the Payment Keys and Secret Key.

3. **Run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

   This will start:
   -   **Frontend**: `http://localhost:8501`
   -   **Backend API**: `http://localhost:8000`
   -   **PostgreSQL**: Port `5432`
   -   **RabbitMQ Management**: `http://localhost:15672` (Login: `guest`/`guest`)
   -   **Redis**: Port `6379`

### Local Development Setup

If you wish to run the backend locally without Docker:

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Configuration**: Ensure your `.env` points to local services (DB, Redis, RabbitMQ).

3. **Run Migrations**:
   ```bash
   python api/migrate.py
   ```

4. **Start Server**:
   ```bash
   uvicorn api.main:app --reload
   ```

### Manual Startup (Using 4 Terminals)

If you prefer running services manually instead of using Docker Compose, open 4 separate terminal windows:

**Terminal 1: Backend API**
```bash
cd api
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2: Frontend Dashboard**
```bash
cd frontend
streamlit run app.py
```

**Terminal 3: Payments Worker (High Priority)**
```bash
# Run from project root
export PYTHONPATH=$PYTHONPATH:$(pwd)/api && celery -A api.worker.celery_app worker -l info -Q payments -n payments@%h
```

**Terminal 4: ML Worker (Resource Heavy)**
```bash
# Run from project root
export PYTHONPATH=$PYTHONPATH:$(pwd)/api && celery -A api.worker.celery_app worker -l info -Q ml -n ml@%h -c 2
```

**Terminal 5: Celery Beat (Periodic Tasks)**
```bash
# Run from project root
export PYTHONPATH=$PYTHONPATH:$(pwd)/api && celery -A api.worker.celery_app beat -l info
```

> **Note**: Ensure RabbitMQ and Redis are running locally or update `.env` to point to their remote URLs.

## 🧪 Testing Suite

The project includes a comprehensive test suite built with **Pytest** and **HTTPX**:

* **High Performance**: Uses an **in-memory SQLite database** (`sqlite+aiosqlite`) for rapid, isolated test execution.
* **Coverage**: Includes unit and integration tests for authentication, credit deduction race conditions, IDOR vulnerabilities, and Celery worker robustness.

Run tests using (inside the container):
```bash
docker-compose exec api pytest
```

Or locally:
```bash
pytest
```

## 📖 API Documentation

Once the server is running, access the interactive documentation at:

* **Swagger UI**: `http://localhost:8000/docs`
* **ReDoc**: `http://localhost:8000/redoc`

## 📝 Usage

1.  Open your browser and navigate to `http://localhost:8501`.
2.  **Register** a new account.
3.  **Login** to access the dashboard.
4.  If you have insufficient credits, go to the "Buy Credits" section in the sidebar.
5.  Enter a Stock Ticker (e.g., `AAPL`, `GOOGL`) and select a model.
6.  Click **Run Prediction**. The request is sent to the backend, processed asynchronously, and the results are displayed.

## To-Do List
1. Add links to jupyter notebooks for prediction services
2. ~~Prediction history - add search by ticker and filter by model type~~
3. Archival storage of prediction history older than 2 months
4. Rewrite frontend in ReactJS
5. ~~Fix: app logs out on reloading~~
6. ~~Improve directional accuracy of transformer model~~
7. Add baseline LSTM model (pre-trained on S&P 500, no on-the-fly training)
8. Automate the retraining of baseline LSTM every 1st of the month using cron job
9. ~~Automate the refund process for failed predictions~~

## 🤝 Contributing

1.  Fork the repository.
2.  Create a feature branch.
3.  Commit your changes.
4.  Push to the branch.
5.  Open a Pull Request.

---
**Disclaimer**: This project is for educational purposes only. Do not use it for financial trading decisions.
