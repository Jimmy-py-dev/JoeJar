def test_root_success(client):
    """Ensures the root health endpoint responds."""
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Inventory Management API"}
