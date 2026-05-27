from app.models.models import AuditLog, Product


# --- 1. TEST LIST PRODUCTS ---

def test_read_products_success(client, mock_session, products_url):
    """Ensures authenticated users can list products."""
    products = [
        Product(id=1, sku="SKU-001", name="Keyboard", price=25.5, stock_quantity=10),
        Product(id=2, sku="SKU-002", name="Mouse", price=12.0, stock_quantity=20),
    ]
    mock_session.exec.return_value.all.return_value = products

    response = client.get(f"{products_url}/")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "sku": "SKU-001", "name": "Keyboard", "price": 25.5, "stock_quantity": 10},
        {"id": 2, "sku": "SKU-002", "name": "Mouse", "price": 12.0, "stock_quantity": 20},
    ]
    mock_session.exec.assert_called_once()


# --- 2. TEST CREATE PRODUCT ---

def test_create_product_success(client, mock_session, products_url):
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

    assert mock_session.add.call_count == 2
    created_product = mock_session.add.call_args_list[0].args[0]
    audit_log = mock_session.add.call_args_list[1].args[0]

    assert isinstance(created_product, Product)
    assert created_product.name == "Monitor"
    assert isinstance(audit_log, AuditLog)
    assert audit_log.action == "PRODUCT_CREATED"
    assert "created product Monitor" in audit_log.description
    assert mock_session.commit.call_count == 2
    mock_session.refresh.assert_called_once_with(created_product)


# --- 3. TEST UPDATE PRODUCT ---

def test_update_product_success(client, mock_session, products_url):
    """Ensures admins can update inventory and price with audit logging."""
    existing_product = Product(
        id=10,
        sku="SKU-010",
        name="Desk",
        price=80.0,
        stock_quantity=3,
    )
    mock_session.get.return_value = existing_product

    response = client.patch(
        f"{products_url}/10",
        json={"price": 95.0, "stock_quantity": 7},
    )

    assert response.status_code == 200
    assert response.json()["price"] == 95.0
    assert response.json()["stock_quantity"] == 7
    assert existing_product.price == 95.0
    assert existing_product.stock_quantity == 7

    mock_session.get.assert_called_once_with(Product, 10)
    assert mock_session.add.call_count == 2
    audit_log = mock_session.add.call_args_list[1].args[0]
    assert isinstance(audit_log, AuditLog)
    assert audit_log.action == "INVENTORY_UPDATE"
    assert "Stock: 3 -> 7" in audit_log.description
    assert "Price: 80.0 -> 95.0" in audit_log.description
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(existing_product)


def test_update_product_not_found(client, mock_session, products_url):
    """Ensures updates return 404 when the product does not exist."""
    mock_session.get.return_value = None

    response = client.patch(f"{products_url}/999", json={"price": 45.0})

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"
    mock_session.get.assert_called_once_with(Product, 999)
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()
