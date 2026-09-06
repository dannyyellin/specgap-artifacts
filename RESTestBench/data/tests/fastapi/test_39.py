"""
Scenario 39: Register a new user via the public signup endpoint using a random email and password. 
Authenticate by obtaining an access token using the login access-token endpoint with that user's credentials. 
Use the returned access token to delete the currently authenticated user via the authenticated delete user me 
endpoint. Verify the delete response status is 200. Verify the response body JSON contains a field "message" 
equal to "User deleted successfully". Then verify that login with the deleted user's credentials fails.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_delete_user_me():
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
    
    # Delete the current user
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/users/me",
        headers=headers
    )
    
    # Verify response
    assert delete_response.status_code == 200
    response_json = delete_response.json()
    assert response_json["message"] == "User deleted successfully"
    
    # Verify that login with deleted user's credentials fails
    login_after_delete = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user_email, "password": user_password}
    )
    assert login_after_delete.status_code == 400, "Login should fail after user is deleted"
