"""
Scenario 61: Attempt to register a user with email set to null.
Verify the response status is 422 (validation error).
"""
import requests

BASE_URL = "http://localhost:8000"


def test_register_null_email():
    # Attempt to register with email set to null
    user_data = {
        "email": None,  # null email
        "password": "validpass123",
        "full_name": "Test User"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json=user_data
    )
    assert response.status_code == 422, f"Expected 422 for null email, got {response.status_code}"
