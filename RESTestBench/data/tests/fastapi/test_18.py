"""
Scenario 18: Authenticate as the superuser (admin@example.com / password123) to obtain an access token, 
then attempt to reset a password using an invalid token. Using the superuser's access token in the 
Authorization header, call the reset-password operation with JSON body {"new_password": "changethis", "token": "invalid"}. 
Verify the response has HTTP status 400, the JSON body contains a "detail" field, and the value of "detail" is exactly "Invalid token".
"""
import requests

BASE_URL = "http://localhost:8000"


def test_reset_password_invalid_token():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Attempt to reset password with invalid token
    reset_response = requests.post(
        f"{BASE_URL}/api/v1/reset-password/",
        headers=headers,
        json={"new_password": "changethis", "token": "invalid"}
    )
    
    # Verify response
    assert reset_response.status_code == 400
    response_json = reset_response.json()
    assert "detail" in response_json
    assert response_json["detail"] == "Invalid token"
