"""
Scenario 31: Sign in using the built-in admin account (username 'admin@example.com', password 'password123') 
to obtain an access token. Using that token, attempt to change the currently authenticated user's password 
by submitting a payload where both the current password and the new password are the same random string 
that does not match the real password. Verify the response status is 400. Verify the response body contains 
a detail message equal to 'Incorrect password'.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_update_password_me_incorrect_password():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Attempt to change password with incorrect current password
    random_password = f"wrongpassword_{uuid.uuid4().hex[:8]}"
    update_response = requests.patch(
        f"{BASE_URL}/api/v1/users/me/password",
        headers=headers,
        json={"current_password": random_password, "new_password": random_password}
    )
    
    # Verify response
    assert update_response.status_code == 400
    response_json = update_response.json()
    assert response_json["detail"] == "Incorrect password"
