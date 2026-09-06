"""
Golden Test for Requirement 11: User Login with Password Verification
Tests that login works with correct password and fails with wrong password.
"""
import requests
import random
import string

BASE_URL = "http://localhost:3000"

def random_suffix():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

def test_user_login_password_verification():
    suffix = random_suffix()
    
    # Create user
    user_data = {
        "user": {
            "username": f"logintest{suffix}",
            "email": f"logintest{suffix}@test.com",
            "password": "correctpass123"
        }
    }
    create_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert create_response.status_code in [200, 201], f"Failed to create user: {create_response.text}"
    
    created_user = create_response.json()["user"]
    assert created_user["username"] == f"logintest{suffix}"
    assert created_user["email"] == f"logintest{suffix}@test.com"
    
    # Login with CORRECT password
    login_data = {
        "user": {
            "email": f"logintest{suffix}@test.com",
            "password": "correctpass123"
        }
    }
    login_response = requests.post(f"{BASE_URL}/api/users/login", json=login_data)
    assert login_response.status_code in [200, 201], f"Expected 200/201, got {login_response.status_code}: {login_response.text}"
    
    login_user = login_response.json()["user"]
    assert login_user["email"] == f"logintest{suffix}@test.com"
    assert login_user["username"] == f"logintest{suffix}"
    assert "token" in login_user, "Response should contain token"
    assert len(login_user["token"]) > 0, "Token should not be empty"
    
    # Login with WRONG password - should fail
    wrong_login_data = {
        "user": {
            "email": f"logintest{suffix}@test.com",
            "password": "wrongpass456"
        }
    }
    wrong_login_response = requests.post(f"{BASE_URL}/api/users/login", json=wrong_login_data)
    assert wrong_login_response.status_code == 401, f"Expected 401 for wrong password, got {wrong_login_response.status_code}"
