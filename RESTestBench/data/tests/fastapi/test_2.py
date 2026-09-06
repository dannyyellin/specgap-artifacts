"""
Scenario 2: Authenticate as a superuser (admin@example.com / password123), create a new item, 
then retrieve the item by its ID. Verify that the response status code is 200 and that the returned 
item's title, description, id, and owner_id exactly match those of the created item.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_read_item():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
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
    assert create_response.status_code == 200
    created_item = create_response.json()
    item_id = created_item["id"]
    
    # Retrieve the item by ID
    read_response = requests.get(
        f"{BASE_URL}/api/v1/items/{item_id}",
        headers=headers
    )
    
    # Verify response
    assert read_response.status_code == 200
    response_json = read_response.json()
    assert response_json["title"] == created_item["title"]
    assert response_json["description"] == created_item["description"]
    assert response_json["id"] == created_item["id"]
    assert response_json["owner_id"] == created_item["owner_id"]
