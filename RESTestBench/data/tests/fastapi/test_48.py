"""
Scenario 48: Attempt to register a new user with password of exactly 129 characters.
Verify the response status is 422 (validation error).
"""
import requests

BASE_URL = "http://localhost:8000"


def test_register_password_too_long_129_chars():
    # Attempt to register with password of exactly 129 characters
    user_data = {
        "email": "test48@example.com",
        "password": "a" * 129,  # exactly 129 characters
        "full_name": "Test User"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json=user_data
    )
    assert response.status_code == 422, f"Expected 422 for 129-char password, got {response.status_code}"
