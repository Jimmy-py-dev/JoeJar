from datetime import datetime, timedelta, timezone

from app.models.models import (
    AuditLog,
    Balance,
    Buyer,
    DiscountType,
    Product,
    Sale,
    SaleItem,
    User,
)


# --- 1. TEST BUYERS ---

def test_read_buyers_success(client, mock_session, sales_url):
    """Ensures authenticated users can list buyer choices."""
    mock_session.exec.return_value.all.return_value = [
        Buyer(id=1, name="Alice", phone=None),
        Buyer(id=2, name="Bob", phone=None),
    ]

    response = client.get(f"{sales_url}/buyers")

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    mock_session.exec.assert_called_once()


# --- 2. TEST SALE CONFIRMATION ---

def test_confirm_sale_paid_success(client, mock_session, sales_url):
    """Ensures a paid sale decrements stock and increases balance on hand."""
    product = Product(id=5, sku="SKU-005", name="Chair", price=50.0, stock_quantity=8)
    balance = Balance(id=1, balance_on_hand=100.0, receivables=25.0)
    mock_session.get.side_effect = [product, balance]

    payload = {
        "buyer_name": "Guest",
        "items": [{"product_id": 5, "quantity": 2, "price": 45.0}],
        "discount_type": "fixed",
        "discount_value": 10.0,
        "payment_method": "cash",
    }

    response = client.post(f"{sales_url}/confirm", json=payload)

    assert response.status_code == 200
    assert response.json()["subtotal"] == 90.0
    assert response.json()["total_price"] == 80.0
    assert response.json()["payment_status"] == "paid"
    assert product.stock_quantity == 6
    assert balance.balance_on_hand == 180.0
    assert mock_session.add.call_count >= 5
    assert any(isinstance(call.args[0], AuditLog) for call in mock_session.add.call_args_list)
    mock_session.commit.assert_called_once()


def test_confirm_sale_credit_adds_receivable(client, mock_session, sales_url):
    """Ensures credit sales are pending and increase receivables."""
    product = Product(id=6, sku="SKU-006", name="Table", price=120.0, stock_quantity=4)
    balance = Balance(id=1, balance_on_hand=0.0, receivables=30.0)
    mock_session.get.side_effect = [product, balance]

    payload = {
        "items": [{"product_id": 6, "quantity": 1, "price": 120.0}],
        "discount_type": "none",
        "discount_value": 0,
        "payment_method": "credit",
    }

    response = client.post(f"{sales_url}/confirm", json=payload)

    assert response.status_code == 200
    assert response.json()["payment_status"] == "pending"
    assert response.json()["total_price"] == 120.0
    assert balance.receivables == 150.0
    mock_session.commit.assert_called_once()


def test_confirm_sale_missing_buyer(client, mock_session, sales_url):
    """Ensures existing buyer IDs must resolve to a buyer."""
    mock_session.get.return_value = None

    response = client.post(
        f"{sales_url}/confirm",
        json={
            "buyer_id": 404,
            "items": [{"product_id": 1, "quantity": 1, "price": 10.0}],
            "payment_method": "cash",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Buyer not found"
    mock_session.commit.assert_not_called()


def test_confirm_sale_missing_product(client, mock_session, sales_url):
    """Ensures sale confirmation fails when a product is missing."""
    mock_session.get.return_value = None

    response = client.post(
        f"{sales_url}/confirm",
        json={
            "buyer_name": "Guest",
            "items": [{"product_id": 999, "quantity": 1, "price": 10.0}],
            "payment_method": "cash",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"
    mock_session.commit.assert_not_called()


# --- 3. TEST SALE HISTORY ---

def test_read_sales_success(client, mock_session, sales_url):
    """Ensures admins can read sale history with seller, buyer, and item names."""
    sale = Sale(
        id=10,
        timestamp=datetime(2026, 5, 2, tzinfo=timezone.utc),
        user_id=1,
        buyer_id=7,
        subtotal=100.0,
        discount_type=DiscountType.FIXED,
        discount_value=5.0,
        total_price=95.0,
        payment_method="cash",
        payment_status="paid",
    )
    item = SaleItem(
        sale_id=10,
        product_id=3,
        quantity=2,
        unit_price_at_sale=50.0,
        master_price_at_sale=55.0,
    )
    mock_session.exec.return_value.all.side_effect = [[sale], [item]]
    mock_session.get.side_effect = [
        User(id=1, username="admin", hashed_password="hash"),
        Buyer(id=7, name="Alice"),
        Product(id=3, sku="SKU-003", name="Monitor", price=55.0, stock_quantity=2),
    ]

    response = client.get(f"{sales_url}/")

    assert response.status_code == 200
    data = response.json()
    assert data[0]["id"] == 10
    assert data[0]["buyer_name"] == "Alice"
    assert data[0]["seller"] == "admin"
    assert data[0]["items"] == [{"item": "Monitor", "quantity": 2, "price": 50.0}]


def test_read_sales_invalid_method(client, sales_url):
    """Ensures unsupported payment filters are rejected."""
    response = client.get(f"{sales_url}/", params={"method": "check"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid payment method filter"


def test_export_sales_success(client, mock_session, sales_url):
    """Ensures sales export returns an Excel attachment."""
    sale = Sale(
        id=11,
        timestamp=datetime.now(),
        user_id=1,
        buyer_id=None,
        subtotal=20.0,
        discount_type=DiscountType.NONE,
        discount_value=0.0,
        total_price=20.0,
        payment_method="bank",
        payment_status="paid",
    )
    item = SaleItem(
        sale_id=11,
        product_id=4,
        quantity=1,
        unit_price_at_sale=20.0,
        master_price_at_sale=20.0,
    )
    mock_session.exec.return_value.all.side_effect = [[sale], [item]]
    mock_session.get.side_effect = [
        User(id=1, username="admin", hashed_password="hash"),
        Product(id=4, sku="SKU-004", name="Cable", price=20.0, stock_quantity=9),
    ]

    response = client.get(f"{sales_url}/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "sales-history-all" in response.headers["content-disposition"]
    assert response.headers["x-deleted-sales-count"] == "0"
    assert response.content


# --- 4. TEST PAYMENT CONFIRMATION ---

def test_confirm_payment_success(client, mock_session, sales_url):
    """Ensures pending credit payments can be confirmed and balance is moved."""
    sale = Sale(
        id=12,
        timestamp=datetime.now(timezone.utc),
        user_id=2,
        buyer_id=None,
        subtotal=75.0,
        discount_type=DiscountType.NONE,
        discount_value=0.0,
        total_price=75.0,
        payment_method="credit",
        payment_status="pending",
    )
    balance = Balance(id=1, balance_on_hand=10.0, receivables=100.0)
    mock_session.get.side_effect = [sale, balance]

    response = client.patch(f"{sales_url}/12/confirm_payment")

    assert response.status_code == 200
    assert response.json()["detail"] == "Payment confirmed successfully"
    assert sale.payment_status == "paid"
    assert balance.balance_on_hand == 85.0
    assert balance.receivables == 25.0
    assert mock_session.add.call_count == 3
    mock_session.commit.assert_called_once()


def test_confirm_payment_sale_not_found(client, mock_session, sales_url):
    """Ensures missing sales return 404 during payment confirmation."""
    mock_session.get.return_value = None

    response = client.patch(f"{sales_url}/999/confirm_payment")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sale not found"
    mock_session.commit.assert_not_called()


def test_confirm_payment_already_paid(client, mock_session, sales_url):
    """Ensures non-pending payments cannot be confirmed twice."""
    sale = Sale(
        id=13,
        timestamp=datetime.now(timezone.utc),
        user_id=2,
        buyer_id=None,
        subtotal=75.0,
        discount_type=DiscountType.NONE,
        discount_value=0.0,
        total_price=75.0,
        payment_method="cash",
        payment_status="paid",
    )
    mock_session.get.return_value = sale

    response = client.patch(f"{sales_url}/13/confirm_payment")

    assert response.status_code == 400
    assert response.json()["detail"] == "Payment already confirmed or not pending"
    mock_session.commit.assert_not_called()


def test_purge_sales_before_current_month_deletes_old_sales(mock_session, mock_admin):
    """Ensures purge deletes old sales/items and rewrites receivables."""
    from app.api.v1.endpoints.sales import purge_sales_before_current_month

    old_sale = Sale(
        id=14,
        timestamp=datetime.now(timezone.utc) - timedelta(days=40),
        user_id=1,
        buyer_id=None,
        subtotal=50.0,
        discount_type=DiscountType.NONE,
        discount_value=0.0,
        total_price=50.0,
        payment_method="cash",
        payment_status="paid",
    )
    sale_item = SaleItem(
        sale_id=14,
        product_id=1,
        quantity=1,
        unit_price_at_sale=50.0,
        master_price_at_sale=50.0,
    )
    balance = Balance(id=1, balance_on_hand=100.0, receivables=50.0)
    mock_session.exec.return_value.all.side_effect = [[old_sale], [sale_item], []]
    mock_session.get.return_value = balance

    deleted_count = purge_sales_before_current_month(mock_session, mock_admin)

    assert deleted_count == 1
    assert mock_session.delete.call_count == 2
    assert balance.receivables == 0
    assert any(isinstance(call.args[0], AuditLog) for call in mock_session.add.call_args_list)
    mock_session.commit.assert_called_once()
