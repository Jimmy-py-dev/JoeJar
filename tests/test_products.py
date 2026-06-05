from sqlmodel import select

from app.models.models import AuditLog, Product


def test_read_products_success(client, db_session, products_url):
    """Ensures authenticated users can list products."""
    db_session.add(Product(sku="SKU-001", name="Keyboard", price=25.5, stock_quantity=10))
    db_session.add(Product(sku="SKU-002", name="Mouse", price=12.0, stock_quantity=20))
    db_session.commit()

    response = client.get(f"{products_url}/")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "sku": "SKU-001", "name": "Keyboard", "price": 25.5, "stock_quantity": 10},
        {"id": 2, "sku": "SKU-002", "name": "Mouse", "price": 12.0, "stock_quantity": 20},
    ]


def test_create_product_success(client, db_session, products_url):
    """Ensures admins can create products and an audit log is recorded."""
    payload = {
        "sku": "SKU-003",
        "name": "Monitor",
        "price": 199.99,
        "stock_quantity": 5,
    }

    response = client.post(f"{products_url}/", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["sku"] == "SKU-003"
    assert data["name"] == "Monitor"
    assert data["price"] == 199.99
    assert data["stock_quantity"] == 5

    db_product = db_session.exec(select(Product).where(Product.sku == "SKU-003")).first()
    assert db_product is not None

    audit_log = db_session.exec(select(AuditLog)).first()
    assert audit_log is not None
    assert audit_log.action == "PRODUCT_CREATED"
    assert "created product Monitor" in audit_log.description


def test_update_product_success(client, db_session, products_url):
    """Ensures admins can update inventory and price with audit logging."""
    product = Product(sku="SKU-010", name="Desk", price=80.0, stock_quantity=3)
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    response = client.patch(
        f"{products_url}/{product.id}",
        json={"price": 95.0, "stock_quantity": 7},
    )

    assert response.status_code == 200
    assert response.json()["price"] == 95.0
    assert response.json()["stock_quantity"] == 7

    db_session.refresh(product)
    assert product.price == 95.0
    assert product.stock_quantity == 7

    audit_log = db_session.exec(select(AuditLog)).first()
    assert audit_log is not None
    assert audit_log.action == "INVENTORY_UPDATE"
    assert "Stock: 3 -> 7" in audit_log.description
    assert "Price: 80.0 -> 95.0" in audit_log.description


def test_update_product_not_found(client, db_session, products_url):
    """Ensures updates return 404 when the product does not exist."""
    response = client.patch(f"{products_url}/999", json={"price": 45.0})

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"
    assert db_session.exec(select(AuditLog)).all() == []
