"""
Scenario 1: Register a new user, then authenticate with that user's credentials and create a new item 
with a specified title and description. Verify that the response status code is 200, and the returned 
item contains the same title and description as the input, the 'id' field is present, and the 'owner_id' 
matches the registered user's ID.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_create_item():
    # Register a new user
    unique_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    user_data = {
        "email": unique_email,
        "password": "testpassword123",
        "full_name": "Test User"
    }
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json=user_data
    )
    assert register_response.status_code == 200
    registered_user = register_response.json()
    user_id = registered_user["id"]
    
    # Authenticate with the new user
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": unique_email, "password": "testpassword123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Create a new item
    item_data = {
        "title": "Test Item",
        "description": "Test Description"
    }
    create_response = requests.post(
        f"{BASE_URL}/api/v1/items/",
        headers=headers,
        json=item_data
    )
    
    # Verify response
    assert create_response.status_code == 200
    response_json = create_response.json()
    assert response_json["title"] == item_data["title"]
    assert response_json["description"] == item_data["description"]
    assert "id" in response_json
    assert "owner_id" in response_json
    # Verify owner_id matches the registered user
    assert response_json["owner_id"] == user_id
