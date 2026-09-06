"""
Scenario 55: Register user, login, then attempt to create item with description of exactly 256 characters.
Verify the response status is 422 (validation error).
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_create_item_description_too_long_256_chars():
    # Register a new user
    unique_email = f"test55_{uuid.uuid4().hex[:8]}@example.com"
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

    # Attempt to create item with description of exactly 256 characters
    item_data = {
        "title": "Valid Title",
        "description": "a" * 256  # exactly 256 characters
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/items/",
        headers=headers,
        json=item_data
    )
    assert response.status_code == 422, f"Expected 422 for 256-char description, got {response.status_code}"
