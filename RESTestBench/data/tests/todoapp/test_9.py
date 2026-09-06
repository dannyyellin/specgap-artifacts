"""
Requirement 9: Updating a todo changes its completion status

Register a user and login. Create a todo (isComplete defaults to false).
Update it with PUT /todos/{id} setting isComplete to true.
Verify response is 200. Then GET /todos/{id} and verify isComplete is true.
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


def test_update_todo_changes_completion_status():
    # Register and login
    email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    token = register_and_login(email, "TestPassword123!")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a todo
    todo_data = {"title": "Original Todo"}
    create_response = requests.post(f"{BASE_URL}/todos", headers=headers, json=todo_data)
    assert create_response.status_code == 201, f"Create failed: {create_response.text}"
    
    created_todo = create_response.json()
    todo_id = created_todo["id"]
    assert created_todo["isComplete"] is False, "New todo should have isComplete=false"
    assert created_todo["title"] == "Original Todo", "New todo should have original title"
    
    # Update the todo to mark as complete and change title
    update_data = {
        "id": todo_id,
        "title": "Updated Todo",
        "isComplete": True
    }
    update_response = requests.put(f"{BASE_URL}/todos/{todo_id}", headers=headers, json=update_data)
    assert update_response.status_code == 200, f"Update failed: {update_response.text}"
    
    # Verify the update
    get_response = requests.get(f"{BASE_URL}/todos/{todo_id}", headers=headers)
    assert get_response.status_code == 200, f"Get failed: {get_response.text}"
    
    updated_todo = get_response.json()
    assert updated_todo["isComplete"] is True, f"isComplete should be true after update, got {updated_todo['isComplete']}"
    assert updated_todo["title"] == "Updated Todo", f"Title should be 'Updated Todo', got {updated_todo['title']}"
