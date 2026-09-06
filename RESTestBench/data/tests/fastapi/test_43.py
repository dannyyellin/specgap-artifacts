"""
Scenario 43: Authenticate as the existing superuser (username 'admin@example.com' and password 'password123') 
to obtain an access token. Use that access token to retrieve the current authenticated user's details and obtain 
the user's id. Using the same superuser access token, attempt to delete the user by id. Verify the response 
status is 403. Verify the response JSON 'detail' field equals 'Super users are not allowed to delete themselves'.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_delete_user_current_super_user_error():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Get current user's ID
    me_response = requests.get(
        f"{BASE_URL}/api/v1/users/me",
        headers=headers
    )
    assert me_response.status_code == 200
    user_id = me_response.json()["id"]
    
    # Attempt to delete the superuser by ID
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/users/{user_id}",
        headers=headers
    )
    
    # Verify response
    assert delete_response.status_code == 403
    response_json = delete_response.json()
    assert response_json["detail"] == "Super users are not allowed to delete themselves"
