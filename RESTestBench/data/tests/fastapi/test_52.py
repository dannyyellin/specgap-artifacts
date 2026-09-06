"""
Scenario 52: Register user, login, then attempt to update password with current_password of exactly 7 characters.
Verify the response status is 422 (validation error).
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_update_password_current_password_too_short_7_chars():
    # Register a new user
    unique_email = f"test52_{uuid.uuid4().hex[:8]}@example.com"
    user_data = {
        "email": unique_email,
        "password": "oldpass123",
        "full_name": "Test User"
    }
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json=user_data
    )
    assert register_response.status_code == 200

    # Login to get token
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": unique_email, "password": "oldpass123"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to update password with current_password of exactly 7 characters
    password_data = {
        "current_password": "1234567",  # exactly 7 characters
        "new_password": "newpass123"
    }
    response = requests.patch(
        f"{BASE_URL}/api/v1/users/me/password",
        headers=headers,
        json=password_data
    )
    assert response.status_code == 422, f"Expected 422 for 7-char current_password, got {response.status_code}"
