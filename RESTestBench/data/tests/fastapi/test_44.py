"""
Scenario 44: Register a new normal user via the user signup endpoint. Authenticate that user to obtain an 
access token via the login access token endpoint. Register a second user via the user signup endpoint. 
Using the first user's access token, attempt to delete the second user by ID. Verify the response status is 403. 
Verify the response JSON contains a 'detail' field equal to "The user doesn't have enough privileges".
Verify the second user still exists by logging in as that user.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_delete_user_without_privileges():
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
    user2_id = register_response2.json()["id"]
    
    # Attempt to delete second user with first user's token
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/users/{user2_id}",
        headers=headers
    )
    
    # Verify response
    assert delete_response.status_code == 403
    response_json = delete_response.json()
    assert response_json["detail"] == "The user doesn't have enough privileges"
    
    # Verify the second user still exists by logging in as that user
    login_response2 = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user2_email, "password": user2_password}
    )
    assert login_response2.status_code == 200, "Second user should still exist and be able to login"
