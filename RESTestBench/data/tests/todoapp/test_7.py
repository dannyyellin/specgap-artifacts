"""
Requirement 7: Deleting a non-existent todo returns 404 Not Found

Register a user and login. Call DELETE /todos/99999 (an ID that doesn't exist).
Verify the response status code is 404 Not Found.
"""
import requests
import uuid

BASE_URL = "http://localhost:5000"


def register_and_login(email, password):
    """Helper to register and login a user, returning access token."""
    user_data = {"email": email, "password": password}
    
    register_response = requests.post(f"{BASE_URL}/users/register", json=user_data)
    assert register_response.status_code == 200, f"Register failed: {register_response.text}"
    
    login_response = requests.post(f"{BASE_URL}/users/login", json=user_data)
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    
    return login_response.json()["accessToken"]


def test_delete_nonexistent_todo_returns_404():
    # Register and login
    email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    token = register_and_login(email, "TestPassword123!")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to delete a non-existent todo
    non_existent_id = 99999
    response = requests.delete(f"{BASE_URL}/todos/{non_existent_id}", headers=headers)
    
    # Verify 404 Not Found
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
