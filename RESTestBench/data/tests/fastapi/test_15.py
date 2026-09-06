"""
Scenario 15: Register a normal user with email test15@example.com. Then request a password recovery 
email to be sent for that email address. Verify that the API responds with HTTP status code 200, 
a JSON message 'Password recovery email sent', and that an email was actually sent to the 
mailcatcher service.
"""
import requests

BASE_URL = "http://localhost:8000"
MAILCATCHER_URL = "http://localhost:1080"


def test_recovery_password():
    # Clear mailcatcher inbox first
    requests.delete(f"{MAILCATCHER_URL}/messages")
    
    # Register a user
    user_email = "test15@example.com"
    user_password = "password123"
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user_email, "password": user_password}
    )
    assert register_response.status_code == 200
    
    # Request password recovery
    recovery_response = requests.post(
        f"{BASE_URL}/api/v1/password-recovery/{user_email}"
    )
    
    # Verify API response
    assert recovery_response.status_code == 200
    response_json = recovery_response.json()
    assert response_json["message"] == "Password recovery email sent"
    
    # Verify email was actually sent via mailcatcher
    messages_response = requests.get(f"{MAILCATCHER_URL}/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) >= 1, "No emails were sent to mailcatcher"
    
    # Check that an email was sent to the correct recipient
    email_found = any(
        user_email in str(msg.get("recipients", []))
        for msg in messages
    )
    assert email_found, f"No email was sent to {user_email}"
