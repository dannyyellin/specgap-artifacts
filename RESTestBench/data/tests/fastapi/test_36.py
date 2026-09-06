"""
Scenario 36: Register a new user with a random email and password. Authenticate as the superuser 
(admin@example.com / password123) to obtain an access token. Using the superuser access token, update 
the registered user by id to set full_name to "Updated_full_name". Verify the update response status is 200. 
Verify the response body contains full_name equal to "Updated_full_name". Then re-fetch the user by id to 
verify the update persisted.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_update_user():
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
    
    # Update the user's full_name
    update_response = requests.patch(
        f"{BASE_URL}/api/v1/users/{user_id}",
        headers=headers,
        json={"full_name": "Updated_full_name"}
    )
    
    # Verify response
    assert update_response.status_code == 200
    response_json = update_response.json()
    assert response_json["full_name"] == "Updated_full_name"
    
    # Re-fetch the user to verify the update persisted
    get_response = requests.get(
        f"{BASE_URL}/api/v1/users/{user_id}",
        headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["full_name"] == "Updated_full_name", "Update should have persisted"
