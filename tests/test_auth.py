from unittest.mock import patch
from app.models.models import User, RefreshToken
from datetime import datetime, timedelta, timezone

# --- 1. TEST REGISTER ENDPOINT ---

def test_register_user_success(client, mock_session, auth_url):
    """Ensures a brand new user can register successfully when admin authorized."""
    # Arrange: Simulate that the database query returns None (user does not exist)
    mock_session.exec.return_value.first.return_value = None
    
    # Mock the internal password hashing function
    with patch("app.core.security.get_password_hash", return_value="hashed_secret") as mock_hash:
        # Act
        payload = {"username": "newuser", "password": "securepassword"}
        response = client.post(f"{auth_url}/register", json=payload)
        
        # Assert response schema details
        assert response.status_code == 200
        # Assert engine behaviors were executed correctly
        mock_hash.assert_called_once_with("securepassword")
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

def test_register_user_already_exists(client, mock_session, auth_url):
    """Ensures registration drops a 400 error if username is taken."""
    # Arrange: Simulate that database returns an existing user object
    existing_user = User(username="taken_name", hashed_password="abc")
    mock_session.exec.return_value.first.return_value = existing_user
    
    # Act
    payload = {"username": "taken_name", "password": "somepassword"}
    response = client.post(f"{auth_url}/register", json=payload)
    
    # Assert
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already taken"


# --- 2. TEST LOGIN ENDPOINT ---

def test_login_success(client, mock_session, auth_url):
    """Ensures valid user credentials generate appropriate auth tokens."""
    # Arrange: Setup simulated user profile 
    fake_user = User(username="testuser", hashed_password="hashed_password")
    fake_user.id = 99
    mock_session.exec.return_value.first.return_value = fake_user
    
    # Wrap utility layers in execution mocks
    with patch("app.core.security.verify_password", return_value=True), \
         patch("app.core.security.create_token", side_effect=["access_jwt", "refresh_jwt"]):
         
        # Act
        form_data = {"username": "testuser", "password": "password123"}
        response = client.post(f"{auth_url}/login", data=form_data) # Form data context uses 'data'
        
        # Assert tokens return as expected
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["access_token"] == "access_jwt"
        assert res_data["refresh_token"] == "refresh_jwt"
        
        # Assert token registration lifecycle was captured to DB
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

def test_login_invalid_credentials(client, mock_session, auth_url):
    """Ensures invalid credentials are rejected."""
    # Arrange: Simulate user retrieval and failed password verification
    fake_user = User(username="testuser", hashed_password="hashed_password")
    mock_session.exec.return_value.first.return_value = fake_user
    
    with patch("app.core.security.verify_password", return_value=False):
        # Act
        form_data = {"username": "testuser", "password": "wrongpassword"}
        response = client.post(f"{auth_url}/login", data=form_data)
        
        # Assert
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid username or password"


# --- 3. TEST REFRESH TOKEN ROTATION ---

def test_refresh_token_rotation_success(client, mock_session, auth_url):
    """Ensures token rotation successfully revokes the old token and issues a new pair."""
    # Arrange: Setup valid, unrevoked database token object
    future_expiry = datetime.now(timezone.utc) + timedelta(days=1)
    fake_db_token = RefreshToken(
        token="old_refresh_jwt", 
        user_id=99, 
        revoked=False, 
        expires_at=future_expiry
    )
    mock_session.exec.return_value.first.return_value = fake_db_token
    
    with patch("app.core.security.create_token", side_effect=["new_access_jwt", "new_refresh_jwt"]):
        # Act
        response = client.post(f"{auth_url}/refresh", params={"token": "old_refresh_jwt"})
        
        # Assert
        assert response.status_code == 200
        assert response.json()["access_token"] == "new_access_jwt"
        assert fake_db_token.revoked is True # Verifies business logic modification
        mock_session.commit.assert_called_once()

def test_refresh_token_invalid(client, mock_session, auth_url):
    """Ensures missing or revoked refresh tokens are rejected."""
    mock_session.exec.return_value.first.return_value = None

    response = client.post(f"{auth_url}/refresh", params={"token": "missing_refresh_jwt"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


# --- 4. TEST LOGOUT ENDPOINT ---

def test_logout_revokes_token(client, mock_session, auth_url):
    """Ensures logout endpoint flags targeted token as revoked."""
    # Arrange
    fake_db_token = RefreshToken(token="active_token", user_id=5, revoked=False)
    mock_session.exec.return_value.first.return_value = fake_db_token
    
    # Act
    response = client.post(f"{auth_url}/logout", params={"token": "active_token"})
    
    # Assert
    assert response.status_code == 200
    assert fake_db_token.revoked is True
    mock_session.commit.assert_called_once()

def test_logout_missing_token_still_succeeds(client, mock_session, auth_url):
    """Ensures logout is idempotent when the token is already absent."""
    mock_session.exec.return_value.first.return_value = None

    response = client.post(f"{auth_url}/logout", params={"token": "missing_token"})

    assert response.status_code == 200
    assert response.json()["detail"] == "Successfully logged out"
    mock_session.commit.assert_not_called()
