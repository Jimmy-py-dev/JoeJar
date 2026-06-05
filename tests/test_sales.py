from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.models.models import (
    AuditLog,
    Balance,
    Buyer,
    DiscountType,
    Product,
    Sale,
    SaleItem,
)


def test_read_buyers_success(client, db_session, sales_url):
    """Ensures authenticated users can list buyer choices."""
    db_session.add(Buyer(name="Alice", phone=None))
    db_session.add(Buyer(name="Bob", phone=None))
    db_session.commit()

    response = client.get(f"{sales_url}/buyers")

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]


def test_confirm_sale_paid_success(client, db_session, sales_url):
    """Ensures a paid sale decrements stock and increases balance on hand."""
    product = Product(sku="SKU-005", name="Chair", price=50.0, stock_quantity=8)
    balance = Balance(id=1, balance_on_hand=100.0, receivables=25.0)
    db_session.add(product)
    db_session.add(balance)
    db_session.commit()
    db_session.refresh(product)

    response = client.post(
        f"{sales_url}/confirm",
        json={
            "buyer_name": "Guest",
            "items": [{"product_id": product.id, "quantity": 2, "price": 45.0}],
            "discount_type": "fixed",
            "discount_value": 10.0,
            "payment_method": "cash",
        },
    )

    assert response.status_code == 200
    assert response.json()["subtotal"] == 90.0
    assert response.json()["total_price"] == 80.0
    assert response.json()["payment_status"] == "paid"

    db_session.refresh(product)
    db_session.refresh(balance)
    assert product.stock_quantity == 6
    assert balance.balance_on_hand == 180.0

    sale_item = db_session.exec(select(SaleItem)).first()
    assert sale_item.quantity == 2
    assert db_session.exec(select(AuditLog).where(AuditLog.action == "PRICE_OVERRIDE")).first()


def test_confirm_sale_credit_adds_receivable(client, db_session, sales_url):
    """Ensures credit sales are pending and increase receivables."""
    product = Product(sku="SKU-006", name="Table", price=120.0, stock_quantity=4)
    balance = Balance(id=1, balance_on_hand=0.0, receivables=30.0)
    db_session.add(product)
    db_session.add(balance)
    db_session.commit()
    db_session.refresh(product)

    response = client.post(
        f"{sales_url}/confirm",
        json={
            "items": [{"product_id": product.id, "quantity": 1, "price": 120.0}],
            "discount_type": "none",
            "discount_value": 0,
            "payment_method": "credit",
        },
    )

    assert response.status_code == 200
    assert response.json()["payment_status"] == "pending"
    assert response.json()["total_price"] == 120.0

    db_session.refresh(balance)
    assert balance.receivables == 150.0


def test_confirm_sale_missing_buyer(client, db_session, sales_url):
    """Ensures existing buyer IDs must resolve to a buyer."""
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
    assert db_session.exec(select(Sale)).all() == []


def test_confirm_sale_missing_product(client, db_session, sales_url):
    """Ensures sale confirmation fails when a product is missing."""
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


def test_read_sales_success(client, db_session, sales_url, mock_admin):
    """Ensures admins can read sale history with seller, buyer, and item names."""
    buyer = Buyer(name="Alice")
    product = Product(sku="SKU-003", name="Monitor", price=55.0, stock_quantity=2)
    db_session.add(buyer)
    db_session.add(product)
    db_session.commit()
    db_session.refresh(buyer)
    db_session.refresh(product)

    sale = Sale(
        timestamp=datetime(2026, 5, 2, tzinfo=timezone.utc),
        user_id=mock_admin.id,
        buyer_id=buyer.id,
        subtotal=100.0,
        discount_type=DiscountType.FIXED,
        discount_value=5.0,
        total_price=95.0,
        payment_method="cash",
        payment_status="paid",
    )
    db_session.add(sale)
    db_session.commit()
    db_session.refresh(sale)
    db_session.add(
        SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity=2,
            unit_price_at_sale=50.0,
            master_price_at_sale=55.0,
        )
    )
    db_session.commit()

    response = client.get(f"{sales_url}/")

    assert response.status_code == 200
    data = response.json()
    assert data[0]["id"] == sale.id
    assert data[0]["buyer_name"] == "Alice"
    assert data[0]["seller"] == "admin"
    assert data[0]["items"] == [{"item": "Monitor", "quantity": 2, "price": 50.0}]


def test_read_sales_invalid_method(client, sales_url):
    """Ensures unsupported payment filters are rejected."""
    response = client.get(f"{sales_url}/", params={"method": "check"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid payment method filter"


def test_export_sales_success(client, db_session, sales_url, mock_admin):
    """Ensures sales export returns an Excel attachment."""
    product = Product(sku="SKU-004", name="Cable", price=20.0, stock_quantity=9)
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    sale = Sale(
        timestamp=datetime.now(timezone.utc),
        user_id=mock_admin.id,
        buyer_id=None,
        subtotal=20.0,
        discount_type=DiscountType.NONE,
        discount_value=0.0,
        total_price=20.0,
        payment_method="bank",
        payment_status="paid",
    )
    db_session.add(sale)
    db_session.commit()
    db_session.refresh(sale)
    db_session.add(
        SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity=1,
            unit_price_at_sale=20.0,
            master_price_at_sale=20.0,
        )
    )
    db_session.commit()

    response = client.get(f"{sales_url}/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "sales-history-all" in response.headers["content-disposition"]
    assert response.headers["x-deleted-sales-count"] == "0"
    assert response.content


def test_confirm_payment_success(client, db_session, sales_url, mock_user):
    """Ensures pending credit payments can be confirmed and balance is moved."""
    balance = Balance(id=1, balance_on_hand=10.0, receivables=100.0)
    sale = Sale(
        timestamp=datetime.now(timezone.utc),
        user_id=mock_user.id,
        buyer_id=None,
        subtotal=75.0,
        discount_type=DiscountType.NONE,
        discount_value=0.0,
        total_price=75.0,
        payment_method="credit",
        payment_status="pending",
    )
    db_session.add(balance)
    db_session.add(sale)
    db_session.commit()
    db_session.refresh(sale)

    response = client.patch(f"{sales_url}/{sale.id}/confirm_payment")

    assert response.status_code == 200
    assert response.json()["detail"] == "Payment confirmed successfully"

    db_session.refresh(sale)
    db_session.refresh(balance)
    assert sale.payment_status == "paid"
    assert balance.balance_on_hand == 85.0
    assert balance.receivables == 25.0
    assert db_session.exec(select(AuditLog).where(AuditLog.action == "PAYMENT_CONFIRMED")).first()


def test_confirm_payment_sale_not_found(client, db_session, sales_url):
    """Ensures missing sales return 404 during payment confirmation."""
    response = client.patch(f"{sales_url}/999/confirm_payment")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sale not found"
    assert db_session.exec(select(AuditLog)).all() == []


def test_confirm_payment_already_paid(client, db_session, sales_url, mock_user):
    """Ensures non-pending payments cannot be confirmed twice."""
    sale = Sale(
        timestamp=datetime.now(timezone.utc),
        user_id=mock_user.id,
        buyer_id=None,
        subtotal=75.0,
        discount_type=DiscountType.NONE,
        discount_value=0.0,
        total_price=75.0,
        payment_method="cash",
        payment_status="paid",
    )
    db_session.add(sale)
    db_session.commit()
    db_session.refresh(sale)

    response = client.patch(f"{sales_url}/{sale.id}/confirm_payment")

    assert response.status_code == 400
    assert response.json()["detail"] == "Payment already confirmed or not pending"


def test_purge_sales_before_current_month_deletes_old_sales(db_session, mock_admin):
    """Ensures purge deletes old sales/items and rewrites receivables."""
    from app.api.v1.endpoints.sales import purge_sales_before_current_month

    product = Product(sku="SKU-001", name="Lamp", price=50.0, stock_quantity=5)
    balance = Balance(id=1, balance_on_hand=100.0, receivables=50.0)
    db_session.add(product)
    db_session.add(balance)
    db_session.commit()
    db_session.refresh(product)

    old_sale = Sale(
        timestamp=datetime.now(timezone.utc) - timedelta(days=40),
        user_id=mock_admin.id,
        buyer_id=None,
        subtotal=50.0,
        discount_type=DiscountType.NONE,
        discount_value=0.0,
        total_price=50.0,
        payment_method="cash",
        payment_status="paid",
    )
    db_session.add(old_sale)
    db_session.commit()
    db_session.refresh(old_sale)
    db_session.add(
        SaleItem(
            sale_id=old_sale.id,
            product_id=product.id,
            quantity=1,
            unit_price_at_sale=50.0,
            master_price_at_sale=50.0,
        )
    )
    db_session.commit()

    deleted_count = purge_sales_before_current_month(db_session, mock_admin)

    assert deleted_count == 1
    assert db_session.exec(select(Sale)).all() == []
    assert db_session.exec(select(SaleItem)).all() == []
    db_session.refresh(balance)
    assert balance.receivables == 0
    assert db_session.exec(select(AuditLog).where(AuditLog.action == "SALES_PURGE")).first()
