"""
Scenario 53: Register user, login, then attempt to create item with empty title.
Verify the response status is 422 (validation error).
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_create_item_empty_title():
    # Register a new user
    unique_email = f"test53_{uuid.uuid4().hex[:8]}@example.com"
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

    # Attempt to create item with empty title
    item_data = {
        "title": "",  # empty string - 0 characters
        "description": "Test description"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/items/",
        headers=headers,
        json=item_data
    )
    assert response.status_code == 422, f"Expected 422 for empty title, got {response.status_code}"
