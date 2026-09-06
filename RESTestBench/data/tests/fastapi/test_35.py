"""
Scenario 35: Attempt to register a user using the existing superuser email 'admin@example.com' with a 
random password and random full name by calling the user registration operation. Verify the response status 
is 400. Verify the response body field 'detail' equals 'The user with this email already exists in the system'.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_register_user_already_exists_error():
    # Attempt to register with existing superuser email
    user_password = "password123"
    user_full_name = f"User {uuid.uuid4().hex[:8]}"
    
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={
            "email": "admin@example.com",
            "password": user_password,
            "full_name": user_full_name
        }
    )
    
    # Verify response
    assert register_response.status_code == 400
    response_json = register_response.json()
    assert response_json["detail"] == "The user with this email already exists in the system"
