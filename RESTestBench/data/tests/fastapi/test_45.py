"""
Scenario 45: Register a new user via signup and authenticate to get a token. Create an item using that token.
Store the item ID from the response. As superuser (admin@example.com / password123), delete the user by ID.
Verify 200 status with message 'User deleted successfully'. Using the superuser token, attempt to GET the item
by ID. Verify it returns 404 with detail 'Item not found'.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_delete_user_cascades_items():
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

    # Authenticate as the new user
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": unique_email, "password": "testpassword123"}
    )
    assert login_response.status_code == 200
    user_token = login_response.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Create an item as the user
    item_data = {
        "title": "User Item To Be Cascaded",
        "description": "This item should be deleted when user is deleted"
    }
    create_response = requests.post(
        f"{BASE_URL}/api/v1/items/",
        headers=user_headers,
        json=item_data
    )
    assert create_response.status_code == 200
    item_id = create_response.json()["id"]

    # Authenticate as superuser
    admin_login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert admin_login_response.status_code == 200
    admin_token = admin_login_response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Delete the user as superuser
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/users/{user_id}",
        headers=admin_headers
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "User deleted successfully"

    # Attempt to GET the item - should return 404
    get_item_response = requests.get(
        f"{BASE_URL}/api/v1/items/{item_id}",
        headers=admin_headers
    )
    assert get_item_response.status_code == 404
    assert get_item_response.json()["detail"] == "Item not found"
