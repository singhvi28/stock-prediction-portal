import pytest
from unittest.mock import MagicMock, patch
from tasks import process_payment
from db import Transaction, User

@pytest.fixture
def mock_redis():
    with patch("tasks.redis_client") as mock:
        yield mock

@pytest.fixture
def mock_session():
    with patch("tasks.db_session") as mock:
        yield mock

def test_process_payment_idempotency(mock_redis):
    # Setup: Redis returns True for processed key
    mock_redis.get.return_value = True

    result = process_payment("pay_123", "order_123")

    assert result == "Already Processed"
    mock_redis.get.assert_called_with("processed:pay_123")
    # Verify no lock attempted
    mock_redis.lock.assert_not_called()

def test_process_payment_locked(mock_redis):
    # Setup: Redis processed key is None
    mock_redis.get.return_value = None
    
    # Setup: Lock acquisition fails
    lock_mock = MagicMock()
    lock_mock.acquire.return_value = False
    mock_redis.lock.return_value = lock_mock

    # Setup: Mock retry to avoid actual retry logic
    with patch("tasks.process_payment.retry", side_effect=Exception("Retry Triggered")) as mock_retry:
        with pytest.raises(Exception, match="Retry Triggered"):
            process_payment("pay_123", "order_123")
        
        mock_retry.assert_called()

def test_process_payment_success(mock_redis, mock_session):
    # 1. Setup Redis
    mock_redis.get.return_value = None
    lock_mock = MagicMock()
    lock_mock.acquire.return_value = True
    mock_redis.lock.return_value = lock_mock

    # 2. Setup DB Data
    mock_txn = MagicMock(spec=Transaction)
    mock_txn.status = "PENDING"
    mock_txn.user_id = 1
    mock_txn.credits = 10
    mock_txn.id = 100
    
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.credits = 5

    # Mock session.scalar (get transaction)
    mock_session.scalar.return_value = mock_txn
    # Mock session.get (get user)
    mock_session.get.return_value = mock_user

    # 3. Execution
    result = process_payment("pay_123", "order_123")

    # 4. Verification
    assert result == "Payment Processed"
    
    # DB Updates
    assert mock_txn.status == "SUCCESS"
    assert mock_txn.razorpay_payment_id == "pay_123"
    assert mock_user.credits == 15 # 5 + 10
    
    # Ledger added
    assert mock_session.add.called
    
    # Redis processed key set
    mock_redis.setex.assert_called_with("processed:pay_123", 604800, "1")
    
    # Lock released
    lock_mock.release.assert_called()

def test_transaction_not_found(mock_redis, mock_session):
    # 1. Setup Redis
    mock_redis.get.return_value = None
    lock_mock = MagicMock()
    lock_mock.acquire.return_value = True
    mock_redis.lock.return_value = lock_mock

    # 2. Setup DB (No transaction found)
    mock_session.scalar.return_value = None

    # 3. Execution
    result = process_payment("pay_123", "order_123")

    # 4. Verification
    assert result == "Transaction Not Found"
    mock_session.add.assert_not_called()
    mock_redis.setex.assert_not_called()
