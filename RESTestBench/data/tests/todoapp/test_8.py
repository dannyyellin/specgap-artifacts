"""
Requirement 8: Users cannot delete another user's todo

Register userA and userB. UserA creates a todo and notes the ID. UserB tries to
DELETE /todos/{id} using userA's todo ID. Verify response is 404.
Then userA verifies their todo still exists via GET /todos/{id}.
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


def test_cannot_delete_another_users_todo():
    # Create userA
    email_a = f"usera_{uuid.uuid4().hex[:8]}@example.com"
    token_a = register_and_login(email_a, "TestPassword123!")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # Create userB
    email_b = f"userb_{uuid.uuid4().hex[:8]}@example.com"
    token_b = register_and_login(email_b, "TestPassword123!")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # UserA creates a todo
    todo_data = {"title": "UserA's Todo"}
    create_response = requests.post(f"{BASE_URL}/todos", headers=headers_a, json=todo_data)
    assert create_response.status_code == 201, f"Create failed: {create_response.text}"
    
    todo_id = create_response.json()["id"]
    
    # UserB tries to delete userA's todo
    delete_response = requests.delete(f"{BASE_URL}/todos/{todo_id}", headers=headers_b)
    
    # Verify 404 Not Found (userB cannot delete userA's todo)
    assert delete_response.status_code == 404, f"Expected 404, got {delete_response.status_code}"
    
    # Verify userA's todo still exists
    get_response = requests.get(f"{BASE_URL}/todos/{todo_id}", headers=headers_a)
    assert get_response.status_code == 200, f"Todo should still exist after failed delete"
    assert get_response.json()["title"] == "UserA's Todo", "Todo content should be unchanged"
