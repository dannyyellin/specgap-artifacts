"""
Scenario 22: Authenticate using the superuser credentials (admin@example.com / password123) to obtain an 
access token. Using that superuser token, create a new user by supplying a randomly generated email and password. 
Verify the create-user request succeeds (response status is in the 200-299 range). Verify the response body 
contains an 'email' field equal to the generated email, an 'id' field is present, and 'is_active' is true.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_create_user_new_email():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Create a new user
    user_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    user_password = "password123"
    create_response = requests.post(
        f"{BASE_URL}/api/v1/users/",
        headers=headers,
        json={"email": user_email, "password": user_password}
    )
    
    # Verify response
    assert 200 <= create_response.status_code < 300
    response_json = create_response.json()
    assert response_json["email"] == user_email
    assert "id" in response_json
    assert response_json["is_active"] == True
