from datetime import datetime, timezone

from app.models.models import AuditLog


def test_get_audit_logs_success(client, mock_session, admin_url):
    """Ensures admins can read audit logs in API format."""
    logs = [
        AuditLog(
            id=1,
            user_id=1,
            action="PRODUCT_CREATED",
            description="admin created product Keyboard",
            timestamp=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
    ]
    mock_session.exec.return_value.all.return_value = logs

    response = client.get(f"{admin_url}/audit-logs")

    assert response.status_code == 200
    assert response.json()[0]["id"] == 1
    assert response.json()[0]["action"] == "PRODUCT_CREATED"
    assert response.json()[0]["description"] == "admin created product Keyboard"
    mock_session.exec.assert_called_once()
