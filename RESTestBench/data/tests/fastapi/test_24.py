"""
Scenario 24: Generate a random email and password. Register a new user with those credentials using the 
public user registration API (users-register_user). Authenticate using the newly registered user's credentials 
to obtain an access token (login-login_access_token). Use the access token in an Authorization Bearer header 
to retrieve the created user by ID (users-read_user_by_id). Verify the retrieval response status code is in 
the 200-299 range. Verify the response body contains an 'email' field equal to the originally generated email 
and the 'id' field matches the created user's id.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_get_existing_user_current_user():
    # Generate random credentials
    user_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    user_password = "password123"
    
    # Register a new user
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user_email, "password": user_password}
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["id"]
    
    # Login as the new user
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user_email, "password": user_password}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Retrieve the user by ID
    read_response = requests.get(
        f"{BASE_URL}/api/v1/users/{user_id}",
        headers=headers
    )
    
    # Verify response
    assert 200 <= read_response.status_code < 300
    response_json = read_response.json()
    assert response_json["email"] == user_email
    assert response_json["id"] == user_id
