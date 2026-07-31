"""
Atomicity of the credit debit in POST /api/predict.

The debit (users.credits + CreditLedger) and the PredictionHistory row must be committed
in a SINGLE transaction. The history row is what makes a debit recoverable: cleanup_stuck_tasks
finds abandoned work by looking for PredictionHistory rows with prediction_data IS NULL.

If the two were committed separately, a crash in between would leave the user debited with no
history row -- the sweeper would never find it and the credits would be lost permanently.
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select, func

from db import User, CreditLedger, PredictionHistory
from utils import hash_password
from conftest import TestingSessionLocal


@pytest.fixture
def mock_celery_apply_async():
    with patch("tasks.predict_task.apply_async") as mock_apply:
        mock_apply.return_value = MagicMock(id="atomic-task-id")
        yield mock_apply


async def _make_user_and_token(client, db_session, email, credits=10):
    user = User(email=email, password_hash=hash_password("password"), credits=credits)
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/auth/login", json={"email": email, "password": "password"})
    token = resp.json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_debit_and_history_share_one_commit(client, db_session, mock_celery_apply_async):
    """The endpoint must reach the broker having committed exactly once."""
    user, headers = await _make_user_and_token(client, db_session, "atomic_one@example.com")

    commits = []
    real_commit = db_session.commit

    async def counting_commit():
        commits.append(1)
        return await real_commit()

    with patch.object(db_session, "commit", counting_commit):
        response = await client.post(
            "/api/predict",
            json={"ticker": "AAPL", "model": "multihead", "lookback": 50},
            headers=headers,
        )

    assert response.status_code == 200, response.text
    assert len(commits) == 1, (
        f"Expected a single commit covering both the debit and the history row, got {len(commits)}. "
        "Separate commits reintroduce the window where credits are lost with nothing to sweep."
    )


@pytest.mark.asyncio
async def test_debit_is_visible_with_its_history_row(client, db_session, mock_celery_apply_async):
    """After a successful request, the ledger row and the history row are both durable."""
    user, headers = await _make_user_and_token(client, db_session, "atomic_two@example.com")

    response = await client.post(
        "/api/predict",
        json={"ticker": "AAPL", "model": "multihead", "lookback": 50},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    task_id = response.json()["task_id"]

    await db_session.refresh(user)
    assert user.credits == 8

    ledger = (await db_session.execute(
        select(CreditLedger).where(CreditLedger.user_id == user.id)
    )).scalars().all()
    assert len(ledger) == 1
    assert ledger[0].amount == -2
    assert ledger[0].reason == "PREDICTION_MULTIHEAD"

    history = (await db_session.execute(
        select(PredictionHistory).where(PredictionHistory.task_id == task_id)
    )).scalars().first()
    assert history is not None, "debit committed without the history row that makes it recoverable"
    assert history.user_id == user.id
    # NULL prediction_data is the marker cleanup_stuck_tasks searches for.
    assert history.prediction_data is None


@pytest.mark.asyncio
async def test_no_orphan_debit_when_history_insert_fails(client, db_session, mock_celery_apply_async):
    """
    If building/inserting the history row blows up, the debit must not be durable.

    This is the regression under test: previously the debit was committed before the history
    row was even constructed, so this failure left an unrecoverable orphan debit.
    """
    user, headers = await _make_user_and_token(client, db_session, "atomic_three@example.com")
    user_id = user.id

    with patch("main.PredictionHistory", side_effect=RuntimeError("boom")):
        response = await client.post(
            "/api/predict",
            json={"ticker": "AAPL", "model": "multihead", "lookback": 50},
            headers=headers,
        )

    assert response.status_code == 500

    # The task must not have been dispatched.
    mock_celery_apply_async.assert_not_called()

    # Read committed state through a separate session. The request's own session still holds
    # the failed work as pending in-memory changes; production discards those when get_db
    # closes the session. What matters is that nothing was committed.
    async with TestingSessionLocal() as fresh:
        credits = await fresh.scalar(select(User.credits).where(User.id == user_id))
        assert credits == 10, "credits were debited despite the request failing"

        ledger_count = await fresh.scalar(
            select(func.count()).select_from(CreditLedger).where(CreditLedger.user_id == user_id)
        )
        assert ledger_count == 0, "orphan ledger row committed without a history row"

        history_count = await fresh.scalar(
            select(func.count()).select_from(PredictionHistory).where(
                PredictionHistory.user_id == user_id
            )
        )
        assert history_count == 0
