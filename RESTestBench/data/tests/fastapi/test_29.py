"""
Scenario 29: Register a new normal user and obtain an access token. Using that access token, update the 
authenticated user's profile to change the email to a random email and change the full name to "Updated Name". 
Verify the update operation returns status 200. Verify the response body has 'email' equal to the random email 
and 'full_name' equal to "Updated Name".
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_update_user_me():
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
    
    # Update the user's profile
    new_email = f"updated_{uuid.uuid4().hex[:8]}@example.com"
    update_response = requests.patch(
        f"{BASE_URL}/api/v1/users/me",
        headers=headers,
        json={"email": new_email, "full_name": "Updated Name"}
    )
    
    # Verify response
    assert update_response.status_code == 200
    response_json = update_response.json()
    assert response_json["email"] == new_email
    assert response_json["full_name"] == "Updated Name"
