"""
Scenario 19: Create a new user using the private user creation operation with payload 
{email: 'pollo@listo.com', password: 'password123', full_name: 'Pollo Listo'}. Verify the response status is 200. 
Parse the response JSON and extract the returned 'id'. Authenticate as the superuser (username 'admin@example.com', 
password 'password123') via the login access token operation to obtain an access token. Use that access token to 
retrieve the created user by id via the read user by id operation. Verify the retrieval response status is 200. 
Verify the retrieved user's 'email' is 'pollo@listo.com' and 'full_name' is 'Pollo Listo'.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_create_private_user():
    # Create a private user with the exact email specified in the scenario
    user_email = "pollo@listo.com"
    create_response = requests.post(
        f"{BASE_URL}/api/v1/private/users/",
        json={
            "email": user_email,
            "password": "password123",
            "full_name": "Pollo Listo"
        }
    )
    
    # Verify creation response
    assert create_response.status_code == 200
    created_user = create_response.json()
    user_id = created_user["id"]
    
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
    
    # Verify retrieval response
    assert read_response.status_code == 200
    response_json = read_response.json()
    assert response_json["email"] == user_email
    assert response_json["full_name"] == "Pollo Listo"
