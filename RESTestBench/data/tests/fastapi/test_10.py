"""
Scenario 10: Attempt to delete an item using superuser authentication (use superuser credentials 
admin@example.com / password123) with a non-existent item ID. Verify that the response status code 
is 404 and the response body contains a 'detail' field with the value 'Item not found'.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_delete_item_not_found():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Attempt to delete a non-existent item
    non_existent_id = str(uuid.uuid4())
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/items/{non_existent_id}",
        headers=headers
    )
    
    # Verify response
    assert delete_response.status_code == 404
    response_json = delete_response.json()
    assert response_json["detail"] == "Item not found"
