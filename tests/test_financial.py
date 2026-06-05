from app.models.models import Balance, DiscountType, Sale


def test_financial_summary_returns_zero_when_balance_missing(client, admin_url):
    """Ensures missing balance rows produce a zeroed summary."""
    response = client.get(f"{admin_url}/financial-summary")

    assert response.status_code == 200
    assert response.json() == {
        "balance_on_hand": 0,
        "receivables": 0,
        "actual_balance": 0,
    }


def test_financial_summary_success(client, db_session, admin_url):
    """Ensures balance and receivables are summarized correctly."""
    db_session.add(Balance(id=1, balance_on_hand=150.0, receivables=25.5))
    db_session.commit()

    response = client.get(f"{admin_url}/financial-summary")

    assert response.status_code == 200
    assert response.json() == {
        "balance_on_hand": 150.0,
        "receivables": 25.5,
        "actual_balance": 175.5,
    }


def test_update_balance_requires_balance(client, db_session, admin_url):
    """Ensures balance update rejects missing balance query param."""
    response = client.patch(f"{admin_url}/update_balance")

    assert response.status_code == 400
    assert response.json()["detail"] == "balance is required"
    assert db_session.get(Balance, 1) is None


def test_update_balance_existing_balance(client, db_session, admin_url):
    """Ensures admins can overwrite balance on hand."""
    db_balance = Balance(id=1, balance_on_hand=10.0, receivables=40.0)
    db_session.add(db_balance)
    db_session.commit()

    response = client.patch(f"{admin_url}/update_balance", params={"balance": 99.5})

    assert response.status_code == 200
    assert response.json() == {
        "balance_on_hand": 99.5,
        "receivables": 40.0,
        "actual_balance": 139.5,
    }
    db_session.refresh(db_balance)
    assert db_balance.balance_on_hand == 99.5


def test_recalculate_receivables_success(client, db_session, admin_url, mock_user):
    """Ensures receivables are recalculated from pending sales."""
    db_balance = Balance(id=1, balance_on_hand=100.0, receivables=0.0)
    db_session.add(db_balance)
    db_session.add(
        Sale(
            user_id=mock_user.id,
            subtotal=73.25,
            discount_type=DiscountType.NONE,
            discount_value=0.0,
            total_price=73.25,
            payment_method="credit",
            payment_status="pending",
        )
    )
    db_session.commit()

    response = client.post(f"{admin_url}/balance/recalculate-receivables")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Receivables synchronized",
        "receivables": 73.25,
    }
    db_session.refresh(db_balance)
    assert db_balance.receivables == 73.25
