"""
Requirement 2: Creating a todo without a title returns a validation error

Register a user and login. Attempt to create a todo without a title (empty or missing).
Verify the response status is 400 Bad Request with validation error details.
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


def test_create_todo_without_title_returns_validation_error():
    # Register and login
    email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    token = register_and_login(email, "TestPassword123!")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Attempt to create todo with empty title
    todo_data = {"title": ""}  # Empty title
    response = requests.post(f"{BASE_URL}/todos", headers=headers, json=todo_data)
    
    # Verify 400 Bad Request
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    
    # Verify response contains validation error details
    error_response = response.json()
    assert "errors" in error_response, "Response should contain 'errors' field"
    assert "Title" in error_response["errors"], "Validation error should mention 'Title' field"
    
    # Verify the exact error message
    title_errors = error_response["errors"]["Title"]
    assert any("The Title field is required" in msg for msg in title_errors), \
        f"Expected 'The Title field is required' in error messages, got: {title_errors}"
