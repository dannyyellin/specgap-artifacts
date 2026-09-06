"""
Scenario 40: Authenticate as the superuser (use credentials admin@example.com / password123 to obtain an 
access token). Using the superuser access token, attempt to delete the authenticated user's own account 
(delete current user). Verify the response status is 403. Verify the response body JSON has a 'detail' field 
equal to 'Super users are not allowed to delete themselves'.
"""
import requests

BASE_URL = "http://localhost:8000"


def test_delete_user_me_as_superuser():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Attempt to delete the superuser's own account
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/users/me",
        headers=headers
    )
    
    # Verify response
    assert delete_response.status_code == 403
    response_json = delete_response.json()
    assert response_json["detail"] == "Super users are not allowed to delete themselves"
