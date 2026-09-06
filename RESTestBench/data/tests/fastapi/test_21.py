"""
Scenario 21: Register a new user via the user registration operation using a test email address and password. 
Obtain an access token for that user via the login access token operation. Using the obtained access token 
in the Authorization header, retrieve the authenticated user's profile via the read current user operation. 
Verify the response body is present (non-empty). Verify the response JSON field "is_active" is True. 
Verify the response JSON field "is_superuser" is False. Verify the response JSON field "email" equals the email 
used when registering the user.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_get_users_normal_user_me():
    # Register a new user
    user_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    user_password = "password123"
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user_email, "password": user_password}
    )
    assert register_response.status_code == 200
    
    # Login as the new user
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user_email, "password": user_password}
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
    assert response_json["is_superuser"] == False
    assert response_json["email"] == user_email
