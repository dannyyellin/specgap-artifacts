"""
Scenario 62: Attempt to register a user with password set to null.
Verify the response status is 422 (validation error).
"""
import requests

BASE_URL = "http://localhost:8000"


def test_register_null_password():
    # Attempt to register with password set to null
    user_data = {
        "email": "test62@example.com",
        "password": None,  # null password
        "full_name": "Test User"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json=user_data
    )
    assert response.status_code == 422, f"Expected 422 for null password, got {response.status_code}"
