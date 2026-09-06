"""
Scenario 26: Authenticate as the superuser (username 'admin@example.com', password 'password123') to obtain 
an access token. Using the superuser access token, create a new user via the create-user API with a generated 
email and password. Then, using the same superuser access token, attempt to create another user with the same 
email and password via the create-user API. Assertions: Verify the response status for the duplicate-creation 
attempt is 400. Verify the response body of the duplicate-creation attempt does not contain the '_id' field.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_create_user_existing_username():
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
    create_response1 = requests.post(
        f"{BASE_URL}/api/v1/users/",
        headers=headers,
        json={"email": user_email, "password": user_password}
    )
    assert create_response1.status_code == 200
    
    # Attempt to create another user with the same email
    create_response2 = requests.post(
        f"{BASE_URL}/api/v1/users/",
        headers=headers,
        json={"email": user_email, "password": user_password}
    )
    
    # Verify response
    assert create_response2.status_code == 400
    response_json = create_response2.json()
    assert "_id" not in response_json
    assert response_json["detail"] == "The user with this email already exists in the system."
