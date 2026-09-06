"""
Requirement 13: Users cannot update another user's todo

Register userA and userB. UserA creates a todo and notes the ID. UserB tries to
PUT /todos/{id} using userA's todo ID. Verify response is 404.
Then userA verifies their todo is unchanged via GET /todos/{id}.
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


def test_cannot_update_another_users_todo():
    # Create userA
    email_a = f"usera_{uuid.uuid4().hex[:8]}@example.com"
    token_a = register_and_login(email_a, "TestPassword123!")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # Create userB
    email_b = f"userb_{uuid.uuid4().hex[:8]}@example.com"
    token_b = register_and_login(email_b, "TestPassword123!")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # UserA creates a todo
    original_title = "UserA's Original Todo"
    todo_data = {"title": original_title}
    create_response = requests.post(f"{BASE_URL}/todos", headers=headers_a, json=todo_data)
    assert create_response.status_code == 201, f"Create failed: {create_response.text}"
    
    created_todo = create_response.json()
    todo_id = created_todo["id"]
    
    # UserB tries to update userA's todo
    update_data = {
        "id": todo_id,
        "title": "Hacked by UserB",
        "isComplete": True
    }
    update_response = requests.put(f"{BASE_URL}/todos/{todo_id}", headers=headers_b, json=update_data)
    
    # Verify 404 Not Found (userB cannot update userA's todo)
    assert update_response.status_code == 404, f"Expected 404, got {update_response.status_code}"
    
    # Verify userA's todo is unchanged
    get_response = requests.get(f"{BASE_URL}/todos/{todo_id}", headers=headers_a)
    assert get_response.status_code == 200, f"Todo should still exist"
    
    unchanged_todo = get_response.json()
    assert unchanged_todo["title"] == original_title, f"Title should be unchanged"
    assert unchanged_todo["isComplete"] is False, f"isComplete should be unchanged"
