"""
Scenario 37: Authenticate as the system superuser using the known credentials (username 'admin@example.com', 
password 'password123') to obtain an access token. With that superuser access token, attempt to update a user 
identified by a newly generated UUID that does not exist in the system. Provide an update payload that sets 
the user's full name to 'Updated_full_name'. Verify the response status is 404. Verify the response body 
contains a field named 'detail' with the exact text: "The user with this id does not exist in the system".
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_update_user_not_exists():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Attempt to update a non-existent user
    non_existent_id = str(uuid.uuid4())
    update_response = requests.patch(
        f"{BASE_URL}/api/v1/users/{non_existent_id}",
        headers=headers,
        json={"full_name": "Updated_full_name"}
    )
    
    # Verify response
    assert update_response.status_code == 404
    response_json = update_response.json()
    assert response_json["detail"] == "The user with this id does not exist in the system"
