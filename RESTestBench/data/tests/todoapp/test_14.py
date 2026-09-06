"""
Requirement 17: Accessing todos without authentication returns 401 Unauthorized

Attempt to access GET /todos without providing an Authorization header.
Verify the response status code is 401 Unauthorized.
"""
import requests

BASE_URL = "http://localhost:5000"


def test_access_todos_without_auth_returns_401():
    # Try to access /todos without authentication
    response = requests.get(f"{BASE_URL}/todos")
    
    # Verify 401 Unauthorized
    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
