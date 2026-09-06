"""
Scenario 9: Authenticate as a superuser (use superuser credentials admin@example.com / password123), 
create an item, then delete the created item using the superuser credentials. Verify that the deletion 
request returns HTTP status code 200 and the response JSON contains the message "Item deleted successfully".
"""
import requests

BASE_URL = "http://localhost:8000"


def test_delete_item():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Create a new item
    item_data = {"title": "Test Item", "description": "Test Description"}
    create_response = requests.post(
        f"{BASE_URL}/api/v1/items/",
        headers=headers,
        json=item_data
    )
    assert create_response.status_code == 200
    item_id = create_response.json()["id"]
    
    # Delete the item
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/items/{item_id}",
        headers=headers
    )
    
    # Verify response
    assert delete_response.status_code == 200
    response_json = delete_response.json()
    assert response_json["message"] == "Item deleted successfully"
    
    # Confirm deletion by attempting to retrieve the item
    get_response = requests.get(
        f"{BASE_URL}/api/v1/items/{item_id}",
        headers=headers
    )
    assert get_response.status_code == 404
