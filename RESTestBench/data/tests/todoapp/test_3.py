"""
Requirement 3: Getting a specific todo by ID returns the correct todo

Register a user and login. Create a todo with a specific title. Use the returned ID
to call GET /todos/{id}. Verify the response contains the correct todo data.
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


def test_get_todo_by_id_returns_correct_todo():
    # Register and login
    email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    token = register_and_login(email, "TestPassword123!")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a todo
    todo_data = {"title": "Specific Todo Item"}
    create_response = requests.post(f"{BASE_URL}/todos", headers=headers, json=todo_data)
    assert create_response.status_code == 201, f"Create failed: {create_response.text}"
    
    created_todo = create_response.json()
    todo_id = created_todo["id"]
    
    # Get the todo by ID
    get_response = requests.get(f"{BASE_URL}/todos/{todo_id}", headers=headers)
    
    # Verify response
    assert get_response.status_code == 200, f"Get failed: {get_response.text}"
    
    retrieved_todo = get_response.json()
    assert retrieved_todo["id"] == todo_id, f"ID mismatch: expected {todo_id}, got {retrieved_todo['id']}"
    assert retrieved_todo["title"] == "Specific Todo Item", f"Title mismatch: {retrieved_todo['title']}"
    assert retrieved_todo["isComplete"] is False, f"isComplete should be false"
