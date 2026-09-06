"""
Scenario 49: Attempt to register a new user with full_name of exactly 256 characters.
Verify the response status is 422 (validation error).
"""
import requests

BASE_URL = "http://localhost:8000"


def test_register_fullname_too_long_256_chars():
    # Attempt to register with full_name of exactly 256 characters
    user_data = {
        "email": "test49@example.com",
        "password": "validpass123",
        "full_name": "a" * 256  # exactly 256 characters
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json=user_data
    )
    assert response.status_code == 422, f"Expected 422 for 256-char full_name, got {response.status_code}"
