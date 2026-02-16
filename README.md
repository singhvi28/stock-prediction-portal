# Stock Prediction Portal

A full-stack machine learning application for predicting stock prices using advanced attention mechanisms. The system features a FastAPI backend with asynchronous task processing via Celery and RabbitMQ, a React frontend for user interaction, and comprehensive user management with Razorpay payment integration.

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
-   **Interactive Dashboard**: Built with React for real-time visualization of historical data and forecast trends.
-   **User Authentication**: Secure JWT-based login, registration, and password reset flows.
-   **Credit System**: Pay-per-use model integrated with Razorpay. Buy credits to run premium predictions.
-   **Secure Financial Logic**:
    -   **Razorpay Integration**: End-to-end payment processing with webhook-driven credit fulfillment.
    -   **Transaction Integrity**: Utilizes **SQLAlchemy row-level locking** (`with_for_update`) to prevent double-spend race conditions.
    -   **Idempotency**: Redis-based locking to prevent duplicate transaction processing.
-   **Asynchronous Processing**: Heavy ML tasks are offloaded to Celery workers (RabbitMQ broker) to ensure a responsive UI.
-   **Scalable Architecture**: Microservices ready with Docker Compose.

## 🛠️ Tech Stack

-   **Frontend**: React, React Router, Recharts, Axios
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
├── frontend/            # React dashboard
│   ├── src/             # Source code
│   │   ├── pages/       # Page components
│   │   ├── components/  # Reusable components
│   │   └── services/    # API client
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

**Prerequisites**: [Docker](https://docs.docker.com/get-docker/) with the Compose plugin (`docker compose`).

1. **Clone the repository**:
   ```bash
   git clone https://github.com/singhvi28/stock-pred.git
   cd stock-pred
   ```

2. **Configure Environment Variables**:

   **Backend** — Create a `.env` file in the `api/` directory:
   ```ini
   # Database
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/stock_db

   # Security
   SECRET_KEY=your_super_secret_key
   ALGORITHM=HS256

   # Payments (Razorpay)
   RAZORPAY_KEY_ID=your_razorpay_key_id
   RAZORPAY_KEY_SECRET=your_razorpay_key_secret

   # Celery / Broker
   RABBITMQ_URL=amqp://guest:guest@localhost:5672//
   REDIS_URL=redis://localhost:6379/0
   ```

   **Frontend** — Create a `.env` file in the `frontend/` directory:
   ```ini
   VITE_API_URL=http://localhost:8001
   VITE_RAZORPAY_KEY_ID=your_razorpay_key_id
   ```

   > **Note**: At minimum you need to provide the Razorpay keys and a `SECRET_KEY`.

3. **Build all images**:
   ```bash
   docker compose build
   ```

4. **Start all services**:
   ```bash
   docker compose up -d
   ```

5. **Verify everything is healthy**:
   ```bash
   docker compose ps
   docker compose logs worker-ml worker-payments --tail 10
   ```

   Once running, the following services are available:

   | Service | URL / Port |
   |---------|-----------|
   | **React Frontend** | `http://localhost:5174` |
   | **Backend API** | `http://localhost:8001` |
   | **Swagger Docs** | `http://localhost:8001/docs` |
   | **PostgreSQL** | `localhost:5433` |
   | **RabbitMQ Management** | `http://localhost:15673` (Login: `guest`/`guest`) |
   | **Redis** | `localhost:6380` |

6. **Stop all services**:
   ```bash
   docker compose down
   ```

   To also remove volumes (database data, etc.):
   ```bash
   docker compose down -v
   ```

---

### Local Development Setup (Without Docker)

**Prerequisites**: PostgreSQL, RabbitMQ, and Redis must be running locally on their default ports (5432, 5672, 6379).

1. **Install Backend Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Frontend Dependencies**:
   ```bash
   cd frontend && npm install && cd ..
   ```

3. **Configure `.env`** files (see Docker Setup step 2 above, using `localhost` hostnames).

4. **Start all services** — open 5 separate terminals:

   **Terminal 1 — Backend API**:
   ```bash
   cd api
   python main.py
   ```

   **Terminal 2 — React Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

   **Terminal 3 — Payments Worker** (high priority, I/O-bound):
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)/api
   celery -A api.worker.celery_app worker -l info -Q payments -n payments@%h
   ```

   **Terminal 4 — ML Worker** (resource heavy, CPU-bound):
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)/api
   celery -A api.worker.celery_app worker -l info -Q ml -n ml@%h -c 2
   ```

   **Terminal 5 — Celery Beat** (periodic cleanup tasks):
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)/api
   celery -A api.worker.celery_app beat -l info
   ```

   > **Note**: Terminals 3–5 must be run from the **project root** directory.

   Once running locally:
   -   **Frontend**: `http://localhost:5173`
   -   **Backend API**: `http://localhost:8000`
   -   **Swagger Docs**: `http://localhost:8000/docs`

## 🧪 Testing Suite

The project includes a comprehensive test suite built with **Pytest** and **HTTPX**:

* **High Performance**: Uses an **in-memory SQLite database** (`sqlite+aiosqlite`) for rapid, isolated test execution.
* **Coverage**: Includes unit and integration tests for authentication, credit deduction race conditions, IDOR vulnerabilities, and Celery worker robustness.

Run tests using (inside the container):
```bash
docker compose exec api pytest
```

Or locally:
```bash
pytest
```

## 📖 API Documentation

Once the server is running, access the interactive documentation at:

* **Swagger UI**: `http://localhost:8001/docs` (Docker) or `http://localhost:8000/docs` (local)
* **ReDoc**: `http://localhost:8001/redoc` (Docker) or `http://localhost:8000/redoc` (local)

## 📝 Usage

1.  Open your browser and navigate to `http://localhost:5174` (Docker) or `http://localhost:5173` (local dev).
2.  **Register** a new account.
3.  **Login** to access the dashboard.
4.  If you have insufficient credits, go to the "Buy Credits" section in the sidebar.
5.  Enter a Stock Ticker (e.g., `AAPL`, `GOOGL`) and select a model.
6.  Click **Run Prediction**. The request is sent to the backend, processed asynchronously, and the results are displayed.

## To-Do List
1. Implement Ngrok solution for real webhook testing (High Priority)
2. Add links to jupyter notebooks for prediction services
3. ~~Prediction history - add search by ticker and filter by model type~~
3. Archival storage of prediction history older than 2 months
4. ~~Rewrite frontend in ReactJS~~
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
