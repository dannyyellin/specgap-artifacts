"""
Scenario 13: Attempt to obtain an access token by logging in with a registered user's 
username but an incorrect password. Verify that the response status code is 400, 
indicating a failed authentication due to invalid credentials.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_get_access_token_incorrect_password():
    # First register a new user
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={
            "email": "testuser13@example.com",
            "password": "correctpassword123",
            "full_name": "Test User 13"
        }
    )
    assert register_response.status_code == 200
    
    # Attempt to authenticate with incorrect password
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "testuser13@example.com", "password": "wrongpassword"}
    )
    
    # Verify response
    assert login_response.status_code == 400
    assert login_response.json()["detail"] == "Incorrect email or password"
