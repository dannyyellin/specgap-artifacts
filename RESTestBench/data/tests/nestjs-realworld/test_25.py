"""
Golden test for Requirement 26: JWT token contains correct payload data
"""

import requests
import pytest
import base64
import json

BASE_URL = "http://localhost:3000"


def test_jwt_contains_correct_payload():
    """
    Test that JWT token contains correct user ID, username, and email in payload.
    
    Mutants:
    - Line 110: username: 'wrong' - wrong username in token
    - Line 111: email: 'wrong@wrong.com' - wrong email in token
    """
    
    # Create user
    user_data = {
        "user": {
            "username": "jwtuser1",
            "email": "jwtuser1@test.com",
            "password": "pass123"
        }
    }
    user_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert user_response.status_code in [200, 201]
    
    user = user_response.json()["user"]
    token = user["token"]
    
    # Decode JWT payload (middle part, base64)
    parts = token.split('.')
    assert len(parts) == 3, "JWT should have 3 parts"
    
    # Add padding if needed for base64 decode
    payload_b64 = parts[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += '=' * padding
    
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    
    # Verify payload contains correct data
    assert "username" in payload, "JWT payload should contain username"
    assert payload["username"] == "jwtuser1", \
        f"Expected username='jwtuser1' in JWT, got '{payload['username']}'"
    
    assert "email" in payload, "JWT payload should contain email"
    assert payload["email"] == "jwtuser1@test.com", \
        f"Expected email='jwtuser1@test.com' in JWT, got '{payload['email']}'"
    
    assert "id" in payload, "JWT payload should contain id"
    
    # Verify the token works - GET /api/user should return same user
    headers = {"Authorization": f"Token {token}"}
    get_response = requests.get(f"{BASE_URL}/api/user", headers=headers)
    assert get_response.status_code == 200
    
    returned_user = get_response.json()["user"]
    assert returned_user["username"] == "jwtuser1", \
        f"Expected username='jwtuser1' from GET /api/user, got '{returned_user['username']}'"
    assert returned_user["email"] == "jwtuser1@test.com", \
        f"Expected email='jwtuser1@test.com' from GET /api/user, got '{returned_user['email']}'"
