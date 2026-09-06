"""
Scenario 11: Register a first user and obtain an access token via the authentication endpoint. 
Using this first user, create an item. Then register a second normal user and obtain an access token 
for this second user. Attempt to delete the item created by the first user using the access token of 
the second normal user who does not have sufficient permissions to delete the item. Verify that the 
response status code is 400 and the response body contains a 'detail' field with the value 'Not enough permissions'.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_delete_item_not_enough_permissions():
    # Register first user
    user1_email = f"user1_{uuid.uuid4().hex[:8]}@example.com"
    user1_password = "password123"
    register_response1 = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user1_email, "password": user1_password}
    )
    assert register_response1.status_code == 200
    
    # Login as first user
    login_response1 = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user1_email, "password": user1_password}
    )
    assert login_response1.status_code == 200
    access_token1 = login_response1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {access_token1}"}
    
    # Create an item with first user
    item_data = {"title": "Test Item", "description": "Test Description"}
    create_response = requests.post(
        f"{BASE_URL}/api/v1/items/",
        headers=headers1,
        json=item_data
    )
    assert create_response.status_code == 200
    item_id = create_response.json()["id"]
    
    # Register second user
    user2_email = f"user2_{uuid.uuid4().hex[:8]}@example.com"
    user2_password = "password123"
    register_response2 = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user2_email, "password": user2_password}
    )
    assert register_response2.status_code == 200
    
    # Login as second user
    login_response2 = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user2_email, "password": user2_password}
    )
    assert login_response2.status_code == 200
    access_token2 = login_response2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {access_token2}"}
    
    # Attempt to delete first user's item with second user's token
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/items/{item_id}",
        headers=headers2
    )
    
    # Verify response
    assert delete_response.status_code == 400
    response_json = delete_response.json()
    assert response_json["detail"] == "Not enough permissions"
