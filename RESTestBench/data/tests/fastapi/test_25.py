"""
Scenario 25: Register a new normal user and obtain an access token via the authentication endpoint. 
Using the obtained token, attempt to retrieve a user by ID using a random UUID that is not the authenticated 
user's ID. Verify the response status is 403. Verify the response body equals {"detail": "The user doesn't have enough privileges"}.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_get_existing_user_permissions_error():
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
    
    # The implementation checks first if the user is superuser before checking if the user exists (actually does not check if the user even exists, thats actually a bug!). Thats why the following is working also!
    # Attempt to retrieve a different user by random UUID
    random_user_id = str(uuid.uuid4())
    read_response = requests.get(
        f"{BASE_URL}/api/v1/users/{random_user_id}",
        headers=headers
    )
    
    # Verify response
    assert read_response.status_code == 403
    response_json = read_response.json()
    assert response_json == {"detail": "The user doesn't have enough privileges"}
