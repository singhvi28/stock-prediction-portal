# Test Suite Documentation

This directory contains the automated unit tests for the Stock Prediction API. The tests are built using `pytest` and `httpx` for async testing, using an in-memory SQLite database to ensure speed and isolation.

## 📂 Test Files

### 1. `test_auth.py`
**Purpose**: Verifies the Authentication & Authorization flows.
*   **`test_register_user`**: Checks valid user registration.
*   **`test_register_existing_email`**: Ensures duplicate emails are rejected (400 Bad Request).
*   **`test_login_success`**: Verifies valid credentials return a JWT access token.
*   **`test_login_invalid_password`**: Verifies invalid credentials return 401 Unauthorized.
*   **`test_forgot_password`**: Checks the password reset token generation flow (emails are mocked).

### 2. `test_prediction.py`
**Purpose**: Verifies the Prediction logic and History storage.
*   **`test_predict_endpoint_success`**:
    *   Mocks the ML service to avoid running heavy models.
    *   Verifies the API structure matches the expected contract.
    *   Checks that predictions are correctly saved to the database.
*   **`test_history_endpoint`**:
    *   Tests that saved predictions can be retrieved.
    *   Verifies filters and specific metrics like `directional_accuracy`.

### 3. `test_credits.py`
**Purpose**: Verifies the Credit Consumption & Payment logic.
*   **`test_insufficient_credits`**:
    *   Ensures API returns `402 Payment Required` when balance < cost.
    *   Verifies the specific error message logic.
*   **`test_credit_deduction_multihead`**:
    *   Mocks a successful Multihead prediction (Cost: 2).
    *   Verifies User balance decreases by 2.
    *   Verifies a `CreditLedger` entry is created with reason `PREDICTION_MULTIHEAD`.
*   **`test_credit_deduction_additive`**:
    *   Mocks a successful Additive prediction (Cost: 3).
    *   Verifies User balance decreases by 3.
*   **`test_refund_on_failure`**:
    *   Simulates a model crash *after* credit deduction.
    *   Verifies that the credits are refunded (Balance remains unchanged).
    *   Checks for the `REFUND_FAILED_PREDICTION` ledger entry.

### 4. `test_worker.py`
**Purpose**: Verifies the Celery background worker logic (Redis + DB).
*   **`test_process_payment_idempotency`**:
    *   Simulates a duplicate webhook event.
    *   Ensures the worker returns "Already Processed" without touching the DB.
*   **`test_process_payment_locked`**:
    *   Simulates a race condition where the resource is already locked.
    *   Verifies that the task raises a `Retry` exception to be requeued.
*   **`test_process_payment_success`**:
    *   Verifies the full happy path:
        1.  Acquires Lock.
        2.  Updates Transaction to `SUCCESS`.
        3.  Adds Credits to User.
        4.  Sets Redis `processed` key.
*   **`test_transaction_not_found`**:
    *   Verifies graceful handling when the transaction ID doesn't exist in the DB.

### 5. `conftest.py`
**Purpose**: Global test configuration and fixtures.
*   Sets up the **Async SQLite** in-memory database.
*   Provides the `client` fixture for making async HTTP requests to the FastAPI app.
*   Handles database creation/teardown for each test function to ensure isolation.

---

### 6. `test_async_prediction.py`
**Purpose**: Verifies the Asynchronous Prediction Flow (API + Worker).
*   **`test_predict_endpoint_dispatch`**:
    *   Verifies `POST /api/predict` returns a `task_id` and status `processing`.
    *   Checks that the Celery task is dispatched with correct arguments.
    *   Ensures credits are deducted immediately upon request.
*   **`test_polling_endpoint_success/processing`**:
    *   Mocks `AsyncResult` states (PENDING, SUCCESS).
    *   Verifies the `GET /api/predict/{task_id}` endpoint returns appropriate status and result data.
*   **`test_predict_task_execution`**:
    *   Validates the worker function logic in isolation.
    *   Ensures DB records (PredictionHistory) are created upon success.

### 7. `test_refund_scenarios.py`
**Purpose**: Validates strict refund logic and prevents double-refund bugs.
*   **`test_double_refund_on_retry`**:
    *   Mocks a task failure loop with retries.
    *   **Logic Verified**: Assert that credits are NOT refunded during intermediate retries (count < max), and ONLY refunded when the task hits the `max_retries` limit.
*   **`test_refund_db_failure`**:
    *   Simulates a database failure during the refund process.
    *   Ensures the task retry mechanism still triggers even if logging the refund fails.

### 8. `test_auth_expiry.py`
**Purpose**: Verifies JWT Token Expiration behavior.
*   **`test_access_with_expired_token`**:
    *   Generates a valid JWT with a past expiration time.
    *   Verifies that the API correctly rejects the token with a `401 Unauthorized` response.

### 9. `test_celery_robustness.py`
**Purpose**: Verifies Celery Worker Robustness and Refund Logic on pure failure.
*   **`test_predict_task_timeout`**:
    *   Simulates a task attempting to run but failing (e.g., timeout or crash) after exhausting retries.
    *   Configures Celery to use in-memory broker/backend for isolation.
    *   Verifies that the user is refunded and a `REFUND_FAILED_TASK` ledger entry is created.

### 10. `test_race_conditions.py`
**Purpose**: Verifies that concurrent requests don't lead to negative balances (Double Spend).
*   **`test_credit_race_condition`**:
    *   Sets up a user with enough credits for only 1 request.
    *   Fires 2 concurrent requests using `asyncio.gather`.
    *   **Logic Verified**: Ensures that the database lock (`with_for_update`) prevents both requests from succeeding.
    *   *Note*: This test uses `sqlite+aiosqlite` which has limitations with `FOR UPDATE` locking compared to production PostgreSQL.

---

## 🐛 Bug Report & Fix Log

During the development of these tests, the following issues were identified and resolved:

### 1. Async Database Token Crash (`MissingGreenlet`)
*   **Issue**: The `forgot_password` endpoint crashed with `sqlalchemy.exc.MissingGreenlet`.
*   **Cause**: The code accessed `user.email` *after* `await db.commit()`.
*   **Fix**: Modified `main.py` to save `user.email` locally before commit.

### 2. Double Refund on Retry
*   **Issue**: Users were refunded on *every* failed attempt, leading to profit if a task retried and failed again.
*   **Cause**: The exception handler in `predict_task` issued a refund before checking retry counts.
*   **Fix**: Added a check `if self.request.retries >= max_retries_limit:` in `api/tasks.py` to ensure refunds only happen once (on the final failure).

### 3. Refund Logic Crash (`UnboundLocalError`)
*   **Issue**: Checkpointing `test_refund_scenarios.py` revealed `UnboundLocalError: local variable 'User' referenced before assignment`.
*   **Cause**: Local imports inside `try` block were not executed before exception handler ran.
*   **Fix**: Removed redundant local imports inside `predict_task` to ensure correct scope.

### 4. Critical Race Condition (Double Spend)
*   **Issue**: Concurrent requests to `/api/predict` could deduct credits multiple times for the same transaction, potentially leading to negative balances.
*   **Cause**: The credit deduction logic read `user.credits` and updated it without a database lock. Simultaneous requests read the same initial value.
*   **Fix**: Added `.with_for_update()` to the user selection query in `api/main.py`. This locks the specific user row for the duration of the transaction, ensuring sequential processing of credit deductions.

### 5. Worker Startup Failure with Async Drivers
*   **Issue**: The Celery worker failed to start when the `DATABASE_URL` contained async drivers (e.g., `sqlite+aiosqlite`), which are used by the FastAPI app but incompatible with the synchronous worker engine.
*   **Cause**: `api/tasks.py` initializes a synchronous SQLAlchemy engine but was receiving an async connection string from the environment.
*   **Fix**: Updated `api/tasks.py` to strip `+aiosqlite` (and `+asyncpg`) from the `DATABASE_URL` before initializing the engine.

