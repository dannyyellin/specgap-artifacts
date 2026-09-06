"""
Scenario 27: Register a new normal user and obtain an access token via the authentication endpoint. 
Using that normal-user access token, attempt to create a new user by calling the create user operation 
with a JSON body containing 'email' (a random email) and 'password' (a random lowercase string). 
Verify the response status is 403.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_create_user_by_normal_user():
    # Register a normal user
    user_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    user_password = "password123"
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user_email, "password": user_password}
    )
    assert register_response.status_code == 200
    
    # Login as the normal user
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user_email, "password": user_password}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Attempt to create a new user with normal user's token
    new_user_email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"
    new_user_password = "password123"
    create_response = requests.post(
        f"{BASE_URL}/api/v1/users/",
        headers=headers,
        json={"email": new_user_email, "password": new_user_password}
    )
    
    # Verify response
    assert create_response.status_code == 403
    assert create_response.json()["detail"] == "The user doesn't have enough privileges"
