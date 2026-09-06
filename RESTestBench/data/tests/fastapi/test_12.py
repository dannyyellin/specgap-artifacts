"""
Scenario 12: Authenticate using superuser credentials (admin@example.com / password123) to obtain an access 
token. Verify the response status code is 200 OK, the response contains an 'access_token' field that is not 
empty, and the 'token_type' field equals 'bearer'.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_get_access_token():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    
    # Verify response
    assert login_response.status_code == 200
    response_json = login_response.json()
    assert "access_token" in response_json
    assert response_json["access_token"] != ""
    assert response_json["token_type"] == "bearer"
    
    # Verify the token works on a protected endpoint
    access_token = response_json["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = requests.get(
        f"{BASE_URL}/api/v1/users/me",
        headers=headers
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "admin@example.com"
