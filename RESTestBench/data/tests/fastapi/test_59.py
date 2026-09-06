"""
Scenario 59: Login as admin, then attempt to GET user by invalid UUID format 'not-a-uuid'.
Verify the response status is 422 (validation error).
"""
import requests

BASE_URL = "http://localhost:8000"


def test_get_user_invalid_uuid_format():
    # Login as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to GET user with invalid UUID format
    response = requests.get(
        f"{BASE_URL}/api/v1/users/not-a-uuid",  # invalid UUID format
        headers=headers
    )
    assert response.status_code == 422, f"Expected 422 for invalid UUID format, got {response.status_code}"
