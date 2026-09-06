"""
Requirement 6: Deleting a todo removes it from the database

Register a user and login. Create a todo and note the ID. Call DELETE /todos/{id}.
Verify response is 200. Then call GET /todos/{id} and verify response is 404.
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


def test_delete_todo_removes_it():
    # Register and login
    email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    token = register_and_login(email, "TestPassword123!")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a todo
    todo_data = {"title": "Todo to Delete"}
    create_response = requests.post(f"{BASE_URL}/todos", headers=headers, json=todo_data)
    assert create_response.status_code == 201, f"Create failed: {create_response.text}"
    
    todo_id = create_response.json()["id"]
    
    # Verify todo exists
    get_response = requests.get(f"{BASE_URL}/todos/{todo_id}", headers=headers)
    assert get_response.status_code == 200, f"Todo should exist before delete"
    
    # Delete the todo
    delete_response = requests.delete(f"{BASE_URL}/todos/{todo_id}", headers=headers)
    assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
    
    # Verify todo is gone
    get_response_after = requests.get(f"{BASE_URL}/todos/{todo_id}", headers=headers)
    assert get_response_after.status_code == 404, f"Todo should be deleted, expected 404 got {get_response_after.status_code}"
