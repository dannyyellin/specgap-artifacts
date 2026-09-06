"""
Scenario 47: Attempt to register a new user with password of exactly 7 characters.
Verify the response status is 422 (validation error).
"""
import requests

BASE_URL = "http://localhost:8000"


def test_register_password_too_short_7_chars():
    # Attempt to register with password of exactly 7 characters
    user_data = {
        "email": "test47@example.com",
        "password": "1234567",  # exactly 7 characters
        "full_name": "Test User"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json=user_data
    )
    assert response.status_code == 422, f"Expected 422 for 7-char password, got {response.status_code}"
