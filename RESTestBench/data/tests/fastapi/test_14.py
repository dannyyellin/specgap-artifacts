"""
Scenario 14: Authenticate as a superuser using existing credentials (admin@example.com / password123) 
to obtain an access token, then use this access token to call the test token endpoint. Verify the response 
status code is 200 and that the response JSON contains the field 'email' with value 'admin@example.com'.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_use_access_token():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test the token
    test_response = requests.post(
        f"{BASE_URL}/api/v1/login/test-token",
        headers=headers
    )
    
    # Verify response
    assert test_response.status_code == 200
    response_json = test_response.json()
    assert response_json["email"] == "admin@example.com"
