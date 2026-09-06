"""
Scenario 9: Verify user creation rejects duplicate username or email.
Create a user (username: 'uniqueuser1', email: 'unique1@test.com', password: 'pass123'). Verify 
status 201. Attempt to create another user with the same username but different email 
(username: 'uniqueuser1', email: 'different@test.com'). Verify the response status is 400. 
Verify the response contains 'Username and email must be unique'. Attempt to create another 
user with different username but same email (username: 'differentuser', email: 'unique1@test.com'). 
Verify the response status is 400. Verify the response contains 'Username and email must be unique'.
"""
import requests

BASE_URL = "http://localhost:3000"


def test_user_creation_rejects_duplicates():
    # Create first user
    user1_data = {
        "user": {
            "username": "uniqueuser1",
            "email": "unique1@test.com",
            "password": "pass123"
        }
    }
    response1 = requests.post(f"{BASE_URL}/api/users", json=user1_data)
    assert response1.status_code == 201, f"Expected 201, got {response1.status_code}: {response1.text}"
    
    # Attempt to create user with same username but different email
    duplicate_username_data = {
        "user": {
            "username": "uniqueuser1",
            "email": "different@test.com",
            "password": "pass123"
        }
    }
    response_dup_username = requests.post(f"{BASE_URL}/api/users", json=duplicate_username_data)
    assert response_dup_username.status_code == 400, f"Expected 400 for duplicate username, got {response_dup_username.status_code}: {response_dup_username.text}"
    assert "Username and email must be unique" in response_dup_username.text, f"Expected 'Username and email must be unique' in response: {response_dup_username.text}"
    
    # Attempt to create user with different username but same email
    duplicate_email_data = {
        "user": {
            "username": "differentuser",
            "email": "unique1@test.com",
            "password": "pass123"
        }
    }
    response_dup_email = requests.post(f"{BASE_URL}/api/users", json=duplicate_email_data)
    assert response_dup_email.status_code == 400, f"Expected 400 for duplicate email, got {response_dup_email.status_code}: {response_dup_email.text}"
    assert "Username and email must be unique" in response_dup_email.text, f"Expected 'Username and email must be unique' in response: {response_dup_email.text}"
