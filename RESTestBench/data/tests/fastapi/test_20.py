"""
Scenario 20: Authenticate as a superuser with username 'admin@example.com' and password 'password123' 
to obtain an access token, then retrieve the currently authenticated user's profile (the "me" resource). 
Verify the response body is present (non-empty). Verify the response JSON 'is_active' is True. 
Verify the response JSON 'is_superuser' is True. Verify the response JSON 'email' equals the configured first superuser.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_get_users_superuser_me():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Get current user profile
    me_response = requests.get(
        f"{BASE_URL}/api/v1/users/me",
        headers=headers
    )
    
    # Verify response
    assert me_response.status_code == 200
    response_json = me_response.json()
    assert response_json is not None
    assert response_json["is_active"] == True
    assert response_json["is_superuser"] == True
    assert response_json["email"] == "admin@example.com"
