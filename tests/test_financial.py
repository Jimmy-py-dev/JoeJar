from app.models.models import Balance


# --- 1. TEST FINANCIAL SUMMARY ---

def test_financial_summary_returns_zero_when_balance_missing(client, mock_session, admin_url):
    """Ensures missing balance rows produce a zeroed summary."""
    mock_session.get.return_value = None

    response = client.get(f"{admin_url}/financial-summary")

    assert response.status_code == 200
    assert response.json() == {
        "balance_on_hand": 0,
        "receivables": 0,
        "actual_balance": 0,
    }
    mock_session.get.assert_called_once_with(Balance, 1)


def test_financial_summary_success(client, mock_session, admin_url):
    """Ensures balance and receivables are summarized correctly."""
    mock_session.get.return_value = Balance(id=1, balance_on_hand=150.0, receivables=25.5)

    response = client.get(f"{admin_url}/financial-summary")

    assert response.status_code == 200
    assert response.json() == {
        "balance_on_hand": 150.0,
        "receivables": 25.5,
        "actual_balance": 175.5,
    }


# --- 2. TEST BALANCE UPDATE ---

def test_update_balance_requires_balance(client, mock_session, admin_url):
    """Ensures balance update rejects missing balance query param."""
    response = client.patch(f"{admin_url}/update_balance")

    assert response.status_code == 400
    assert response.json()["detail"] == "balance is required"
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


def test_update_balance_existing_balance(client, mock_session, admin_url):
    """Ensures admins can overwrite balance on hand."""
    db_balance = Balance(id=1, balance_on_hand=10.0, receivables=40.0)
    mock_session.get.return_value = db_balance

    response = client.patch(f"{admin_url}/update_balance", params={"balance": 99.5})

    assert response.status_code == 200
    assert response.json() == {
        "balance_on_hand": 99.5,
        "receivables": 40.0,
        "actual_balance": 139.5,
    }
    assert db_balance.balance_on_hand == 99.5
    mock_session.add.assert_called_once_with(db_balance)
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(db_balance)


def test_recalculate_receivables_success(client, mock_session, admin_url):
    """Ensures receivables are recalculated from pending sales."""
    db_balance = Balance(id=1, balance_on_hand=100.0, receivables=0.0)
    mock_session.exec.return_value.first.return_value = 73.25
    mock_session.get.return_value = db_balance

    response = client.post(f"{admin_url}/balance/recalculate-receivables")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Receivables synchronized",
        "receivables": 73.25,
    }
    assert db_balance.receivables == 73.25
    mock_session.add.assert_called_once_with(db_balance)
    mock_session.commit.assert_called_once()
