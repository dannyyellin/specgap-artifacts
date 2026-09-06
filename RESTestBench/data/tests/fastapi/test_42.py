"""
Scenario 42: Authenticate as the existing superuser (username 'admin@example.com', password 'password123') 
to obtain an access token. Using the superuser access token in the request headers, attempt to delete a user 
by a newly generated random UUID (a user that does not exist). Verify the response status is 404. 
Verify the response JSON body contains a 'detail' field equal to 'User not found'.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_delete_user_not_found():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Attempt to delete a non-existent user
    non_existent_id = str(uuid.uuid4())
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/users/{non_existent_id}",
        headers=headers
    )
    
    # Verify response
    assert delete_response.status_code == 404
    response_json = delete_response.json()
    assert response_json["detail"] == "User not found"
