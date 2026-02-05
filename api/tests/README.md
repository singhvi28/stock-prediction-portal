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

### 3. `conftest.py`
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

