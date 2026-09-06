"""
Scenario 34: Generate a random email, a random password, and a random full name. Register a new user using 
the user registration endpoint with a payload containing 'email' (the generated email), 'password' (the 
generated password), and 'full_name' (the generated full name). Verify the response status is 200. 
Verify the response body 'email' equals the generated email. Verify the response body 'full_name' equals 
the generated full name. Then verify the user can login with the generated credentials.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_register_user():
    # Generate random credentials
    user_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    user_password = "password123"
    user_full_name = f"User {uuid.uuid4().hex[:8]}"
    
    # Register a new user
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={
            "email": user_email,
            "password": user_password,
            "full_name": user_full_name
        }
    )
    
    # Verify response
    assert register_response.status_code == 200
    response_json = register_response.json()
    assert response_json["email"] == user_email
    assert response_json["full_name"] == user_full_name
    
    # Verify the user can login with the generated credentials
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user_email, "password": user_password}
    )
    assert login_response.status_code == 200, "User should be able to login after registration"
    assert "access_token" in login_response.json()
