"""
Scenario 6: Authenticate as a superuser with username 'admin@example.com' and password 'password123', 
create a new item, then update the item's title and description using the superuser credentials. 
Verify that the update operation returns HTTP status code 200, and the response body contains the 
updated title and description fields matching the input, as well as the item's id and owner_id fields 
matching the original item.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_update_item():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Create a new item
    item_data = {"title": "Original Title", "description": "Original Description"}
    create_response = requests.post(
        f"{BASE_URL}/api/v1/items/",
        headers=headers,
        json=item_data
    )
    assert create_response.status_code == 200
    created_item = create_response.json()
    item_id = created_item["id"]
    owner_id = created_item["owner_id"]
    
    # Update the item
    update_data = {"title": "Updated Title", "description": "Updated Description"}
    update_response = requests.put(
        f"{BASE_URL}/api/v1/items/{item_id}",
        headers=headers,
        json=update_data
    )
    
    # Verify response
    assert update_response.status_code == 200
    response_json = update_response.json()
    assert response_json["title"] == update_data["title"]
    assert response_json["description"] == update_data["description"]
    assert response_json["id"] == item_id
    assert response_json["owner_id"] == owner_id
