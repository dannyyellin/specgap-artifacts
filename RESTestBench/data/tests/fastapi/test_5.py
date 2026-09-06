"""
Scenario 5: Authenticate as a superuser using the credentials (username 'admin@example.com', 
password 'password123') to obtain an access token. Create two items in the database using the 
superuser credentials. Then retrieve the list of items with the superuser token. Verify that the 
response status code is 200 OK and that the returned data contains at least the two items that were created.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_read_items():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Create first item
    item_data1 = {"title": "Test Item 1", "description": "Test Description 1"}
    create_response1 = requests.post(
        f"{BASE_URL}/api/v1/items/",
        headers=headers,
        json=item_data1
    )
    assert create_response1.status_code == 200
    item1_id = create_response1.json()["id"]
    
    # Create second item
    item_data2 = {"title": "Test Item 2", "description": "Test Description 2"}
    create_response2 = requests.post(
        f"{BASE_URL}/api/v1/items/",
        headers=headers,
        json=item_data2
    )
    assert create_response2.status_code == 200
    item2_id = create_response2.json()["id"]
    
    # Retrieve all items
    read_response = requests.get(
        f"{BASE_URL}/api/v1/items/",
        headers=headers
    )
    
    # Verify response
    assert read_response.status_code == 200
    response_json = read_response.json()
    
    # Verify count matches data length
    assert response_json["count"] == len(response_json["data"])
    assert response_json["count"] >= 2
    
    # Verify both items appear with correct data
    items_by_id = {item["id"]: item for item in response_json["data"]}
    assert item1_id in items_by_id
    assert item2_id in items_by_id
    assert items_by_id[item1_id]["title"] == "Test Item 1"
    assert items_by_id[item2_id]["title"] == "Test Item 2"
    assert items_by_id[item1_id]["description"] == "Test Description 1"
    assert items_by_id[item2_id]["description"] == "Test Description 2"
