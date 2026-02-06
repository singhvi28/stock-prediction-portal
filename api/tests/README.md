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

## 🐛 Bug Report & Fix Log

During the development of these tests, the following issues were identified and resolved:

### 1. Async Database Token Crash (`MissingGreenlet`)
*   **Issue**: The `forgot_password` endpoint crashed with `sqlalchemy.exc.MissingGreenlet`.
*   **Cause**: The code accessed `user.email` *after* `await db.commit()`. In SQLAlchemy Async, committed objects are expired. Accessing their attributes triggers a lazy load, which fails without an active awaitable context (greenlet).
*   **Fix**: Modified `main.py` to save `user.email` into a local variable `recipient_email` **before** the commit, ensuring safe access for the email sending function.

