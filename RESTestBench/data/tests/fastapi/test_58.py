"""
Scenario 58: Register user, login, then attempt to update profile with invalid email format 'invalid@'.
Verify the response status is 422 (validation error).
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_update_user_me_invalid_email_format():
    # Register a new user
    unique_email = f"test58_{uuid.uuid4().hex[:8]}@example.com"
    user_data = {
        "email": unique_email,
        "password": "validpass123",
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
        data={"username": unique_email, "password": "validpass123"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to update profile with invalid email format
    update_data = {
        "email": "invalid@"  # invalid email format
    }
    response = requests.patch(
        f"{BASE_URL}/api/v1/users/me",
        headers=headers,
        json=update_data
    )
    assert response.status_code == 422, f"Expected 422 for invalid email format, got {response.status_code}"
