"""
Scenario 16: Attempt to recover the password for a non-existent user with the email 'jVgQr@example.com'. 
Verify that the password recovery request returns an HTTP 404 status code indicating the user does not exist.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_recovery_password_user_not_exists():
    # Attempt to recover password for non-existent user
    recovery_response = requests.post(
        f"{BASE_URL}/api/v1/password-recovery/jVgQr@example.com"
    )
    
    # Verify response
    assert recovery_response.status_code == 404
    assert recovery_response.json()["detail"] == "The user with this email does not exist in the system."
