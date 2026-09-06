"""
Scenario 23: Register a new normal user. Authenticate as the superuser (admin@example.com / password123) 
to obtain an access token. Then retrieve that registered user by its ID using the superuser access token. 
Verify the HTTP response status is a success (status code in the 200-299 range). Verify the response body 
contains an 'email' field equal to the email of the user that was created, the 'id' matches the created user's 
id, and 'is_active' is true.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_get_existing_user():
    # Register a new user
    user_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    user_password = "password123"
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user_email, "password": user_password}
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["id"]
    
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
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
    assert response_json["is_active"] == True
