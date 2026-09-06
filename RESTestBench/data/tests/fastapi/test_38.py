"""
Scenario 38: Register two distinct users via the public signup operation, each with a different email and password. 
Authenticate as the superuser (admin@example.com / password123) to obtain an access token. Using the superuser 
access token, attempt to update the first registered user's email (update by id) so that it becomes the second 
user's email. Verify the response status is 409. Verify the response body contains a "detail" field equal to 
"User with this email already exists".
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_update_user_email_exists():
    # Register first user
    user1_email = f"user1_{uuid.uuid4().hex[:8]}@example.com"
    user1_password = "password123"
    register_response1 = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user1_email, "password": user1_password}
    )
    assert register_response1.status_code == 200
    user1_id = register_response1.json()["id"]
    
    # Register second user
    user2_email = f"user2_{uuid.uuid4().hex[:8]}@example.com"
    user2_password = "password123"
    register_response2 = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user2_email, "password": user2_password}
    )
    assert register_response2.status_code == 200
    
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Attempt to update first user's email to second user's email
    update_response = requests.patch(
        f"{BASE_URL}/api/v1/users/{user1_id}",
        headers=headers,
        json={"email": user2_email}
    )
    
    # Verify response
    assert update_response.status_code == 409
    response_json = update_response.json()
    assert response_json["detail"] == "User with this email already exists"
