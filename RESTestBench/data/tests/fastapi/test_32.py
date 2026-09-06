"""
Scenario 32: Register a new normal user and obtain an access token. Register a second user with a different 
random email. Using the access token for the first (authenticated) user, attempt to update the authenticated 
user's email to the email of the already-registered second user. Verify the response status is 409. 
Verify the response body contains a JSON field "detail" with the value "User with this email already exists".
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_update_user_me_email_exists():
    # Register first user
    user1_email = f"user1_{uuid.uuid4().hex[:8]}@example.com"
    user1_password = "password123"
    register_response1 = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user1_email, "password": user1_password}
    )
    assert register_response1.status_code == 200
    
    # Login as first user
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user1_email, "password": user1_password}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Register second user
    user2_email = f"user2_{uuid.uuid4().hex[:8]}@example.com"
    user2_password = "password123"
    register_response2 = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user2_email, "password": user2_password}
    )
    assert register_response2.status_code == 200
    
    # Attempt to update first user's email to second user's email
    update_response = requests.patch(
        f"{BASE_URL}/api/v1/users/me",
        headers=headers,
        json={"email": user2_email}
    )
    
    # Verify response
    assert update_response.status_code == 409
    response_json = update_response.json()
    assert response_json["detail"] == "User with this email already exists"
