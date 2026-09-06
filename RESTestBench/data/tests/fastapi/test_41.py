"""
Scenario 41: Register a new user with a random email and password using the API's user registration operation 
and capture the created user's id. Authenticate as the superuser (username 'admin@example.com', password 
'password123') to obtain an access token and include that token in request headers. Using the superuser 
credentials, delete the previously registered user by its id. Verify the delete operation response status is 200. 
Verify the response body contains a field "message" with value "User deleted successfully". Then verify the 
user was actually deleted by attempting to login as the deleted user (should fail with 400).
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_delete_user_super_user():
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
    
    # Delete the user
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/users/{user_id}",
        headers=headers
    )
    
    # Verify response
    assert delete_response.status_code == 200
    response_json = delete_response.json()
    assert response_json["message"] == "User deleted successfully"
    
    # Verify the user was actually deleted by attempting to login
    login_deleted_user = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user_email, "password": user_password}
    )
    assert login_deleted_user.status_code == 400, "Login should fail for deleted user"
