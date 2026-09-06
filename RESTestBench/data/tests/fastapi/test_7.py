"""
Scenario 7: Authenticate as a superuser (admin@example.com / password123). Then create a Item. 
Attempt to update an item with a non-existent item ID. Verify that the API responds with HTTP 
status code 404 and the response body contains a 'detail' field with the value 'Item not found'.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_update_item_not_found():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Attempt to update a non-existent item
    non_existent_id = str(uuid.uuid4())
    update_data = {"title": "Updated Title", "description": "Updated Description"}
    update_response = requests.put(
        f"{BASE_URL}/api/v1/items/{non_existent_id}",
        headers=headers,
        json=update_data
    )
    
    # Verify response
    assert update_response.status_code == 404
    response_json = update_response.json()
    assert response_json["detail"] == "Item not found"
