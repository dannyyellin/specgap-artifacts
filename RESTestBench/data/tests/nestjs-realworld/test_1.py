"""
Scenario 1: Create a new user and verify the user is stored correctly.
Create a new user using the user creation endpoint with payload {user: {username: 'testuser123', 
email: 'test@example.com', password: 'password123'}}. Verify the response status is 201. 
Parse the response JSON and verify that the returned user object contains 'username' equal to 
'testuser123', 'email' equal to 'test@example.com', and 'token' field is not empty. Extract the 
token from the response. Use the token to retrieve the current user information via the 
GET /api/user endpoint with Authorization header 'Token {token}'. Verify the retrieval response 
status is 200. Verify the retrieved user's 'username' is 'testuser123' and 'email' is 'test@example.com'.
"""
import requests
import uuid

BASE_URL = "http://localhost:3000"


def test_create_and_retrieve_user():
    # Use static values for mutation testing
    username = "testuser123"
    email = "test@example.com"
    password = "password123"
    
    # Create a new user
    user_data = {
        "user": {
            "username": username,
            "email": email,
            "password": password
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/api/users",
        json=user_data
    )
    
    # Verify response status code is 201 (Created)
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    
    response_json = response.json()
    
    # Verify response contains user object
    assert "user" in response_json, "Response should contain 'user' object"
    user = response_json["user"]
    
    # Verify username matches
    assert "username" in user, "User object should contain 'username' field"
    assert user["username"] == username, f"Expected username '{username}', got '{user['username']}'"
    
    # Verify email matches
    assert "email" in user, "User object should contain 'email' field"
    assert user["email"] == email, f"Expected email '{email}', got '{user['email']}'"
    
    # Verify token is present and not empty
    assert "token" in user, "User object should contain 'token' field"
    assert user["token"] is not None, "Token should not be None"
    assert user["token"] != "", "Token should not be empty"
    
    # Extract the token
    token = user["token"]
    
    # Retrieve the current user using the token
    headers = {
        "Authorization": f"Token {token}"
    }
    
    retrieve_response = requests.get(
        f"{BASE_URL}/api/user",
        headers=headers
    )
    
    # Verify retrieval response status is 200
    assert retrieve_response.status_code == 200, f"Expected 200, got {retrieve_response.status_code}: {retrieve_response.text}"
    
    retrieve_json = retrieve_response.json()
    
    # Verify retrieved user data
    assert "user" in retrieve_json, "Retrieved response should contain 'user' object"
    retrieved_user = retrieve_json["user"]
    
    # Verify username matches
    assert "username" in retrieved_user, "Retrieved user should contain 'username' field"
    assert retrieved_user["username"] == username, f"Expected username '{username}', got '{retrieved_user['username']}'"
    
    # Verify email matches
    assert "email" in retrieved_user, "Retrieved user should contain 'email' field"
    assert retrieved_user["email"] == email, f"Expected email '{email}', got '{retrieved_user['email']}'"
