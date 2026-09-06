"""
Requirement 1: Getting all todos returns only the current user's todos

Register two users (userA and userB). UserA creates a todo. UserB creates a different todo.
When userA calls GET /todos, verify only userA's todo is returned (not userB's).
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


def test_get_todos_returns_only_owned_todos():
    # Create userA
    email_a = f"usera_{uuid.uuid4().hex[:8]}@example.com"
    token_a = register_and_login(email_a, "TestPassword123!")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # Create userB
    email_b = f"userb_{uuid.uuid4().hex[:8]}@example.com"
    token_b = register_and_login(email_b, "TestPassword123!")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # UserA creates a todo
    todo_a = {"title": "UserA's Todo"}
    response_a = requests.post(f"{BASE_URL}/todos", headers=headers_a, json=todo_a)
    assert response_a.status_code == 201, f"UserA create failed: {response_a.text}"
    created_todo_a = response_a.json()
    
    # UserB creates a todo
    todo_b = {"title": "UserB's Todo"}
    response_b = requests.post(f"{BASE_URL}/todos", headers=headers_b, json=todo_b)
    assert response_b.status_code == 201, f"UserB create failed: {response_b.text}"
    
    # UserA gets their todos - should only see their own
    get_response = requests.get(f"{BASE_URL}/todos", headers=headers_a)
    assert get_response.status_code == 200, f"Get todos failed: {get_response.text}"
    
    todos = get_response.json()
    assert isinstance(todos, list), "Response should be a list"
    
    # Verify userA only sees their todo
    todo_titles = [t["title"] for t in todos]
    assert "UserA's Todo" in todo_titles, "UserA's todo should be in the list"
    assert "UserB's Todo" not in todo_titles, "UserB's todo should NOT be in the list"
    
    # Verify the todo has correct structure
    user_a_todo = next(t for t in todos if t["title"] == "UserA's Todo")
    assert user_a_todo["id"] == created_todo_a["id"], "Todo ID should match"
