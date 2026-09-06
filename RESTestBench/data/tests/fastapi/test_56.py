"""
Scenario 56: Attempt to reset password with new_password of exactly 7 characters.
Verify the response status is 422 (validation error).
"""
import requests

BASE_URL = "http://localhost:8000"


def test_reset_password_new_password_too_short_7_chars():
    # Attempt to reset password with new_password of exactly 7 characters
    # Note: Token validation happens after field validation, so 422 should be returned first
    reset_data = {
        "token": "fake-token",
        "new_password": "1234567"  # exactly 7 characters
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/reset-password/",
        json=reset_data
    )
    assert response.status_code == 422, f"Expected 422 for 7-char new_password, got {response.status_code}"
