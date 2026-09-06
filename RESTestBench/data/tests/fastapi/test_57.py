"""
Scenario 57: Attempt to register a user with invalid email format 'not-an-email'.
Verify the response status is 422 (validation error).
"""
import requests

BASE_URL = "http://localhost:8000"


def test_register_invalid_email_format():
    # Attempt to register with invalid email format
    user_data = {
        "email": "not-an-email",  # invalid email format
        "password": "validpass123",
        "full_name": "Test User"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json=user_data
    )
    assert response.status_code == 422, f"Expected 422 for invalid email format, got {response.status_code}"
