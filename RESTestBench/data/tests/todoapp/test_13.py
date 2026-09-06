"""
Requirement 14: Registering a user with valid credentials succeeds

Register a new user with valid email and password.
Verify the response status code is 200.
"""
import requests
import uuid

BASE_URL = "http://localhost:5000"


def test_register_user_with_valid_credentials():
    # Generate unique email
    unique_email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"
    
    user_data = {
        "email": unique_email,
        "password": "SecurePassword123!"
    }
    
    # Register the user
    response = requests.post(f"{BASE_URL}/users/register", json=user_data)
    
    # Verify success
    assert response.status_code == 200, f"Registration failed: {response.status_code}: {response.text}"
