from datetime import datetime, timezone

from app.models.models import AuditLog


def test_get_audit_logs_success(client, db_session, admin_url, mock_admin):
    """Ensures admins can read audit logs in API format."""
    db_session.add(
        AuditLog(
            user_id=mock_admin.id,
            action="PRODUCT_CREATED",
            description="admin created product Keyboard",
            timestamp=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    response = client.get(f"{admin_url}/audit-logs")

    assert response.status_code == 200
    assert response.json()[0]["id"] == 1
    assert response.json()[0]["action"] == "PRODUCT_CREATED"
    assert response.json()[0]["description"] == "admin created product Keyboard"
