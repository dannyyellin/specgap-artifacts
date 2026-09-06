"""
Scenario 33: Authenticate as the superuser (use superuser credentials admin@example.com / password123) 
to obtain an access token. Using that access token, invoke the update own password operation for the 
authenticated user with a payload where 'current_password' and 'new_password' are both set to the 
configured first superuser password. Verify the response status is 400. Verify the response JSON body 
contains a 'detail' field equal to 'New password cannot be the same as the current one'.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_update_password_me_same_password_error():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Attempt to change password to the same password
    update_response = requests.patch(
        f"{BASE_URL}/api/v1/users/me/password",
        headers=headers,
        json={"current_password": "password123", "new_password": "password123"}
    )
    
    # Verify response
    assert update_response.status_code == 400
    response_json = update_response.json()
    assert response_json["detail"] == "New password cannot be the same as the current one"
