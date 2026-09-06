"""
Scenario 60: Register user, login, then attempt to GET item by invalid UUID format 'not-a-uuid'.
Verify the response status is 422 (validation error).
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_get_item_invalid_uuid_format():
    # Register a new user
    unique_email = f"test60_{uuid.uuid4().hex[:8]}@example.com"
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

    # Attempt to GET item with invalid UUID format
    response = requests.get(
        f"{BASE_URL}/api/v1/items/not-a-uuid",  # invalid UUID format
        headers=headers
    )
    assert response.status_code == 422, f"Expected 422 for invalid UUID format, got {response.status_code}"
