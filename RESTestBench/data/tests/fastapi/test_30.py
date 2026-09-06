"""
Scenario 30: Authenticate using the existing superuser credentials (admin@example.com / password123) to obtain 
an access token. Using that superuser access token, update the superuser's own password by supplying the current 
password and a newly generated password. Verify the response status is 200 and the response body contains a field 
'message' equal to 'Password updated successfully'. Then verify that login with the NEW password succeeds. 
Finally, revert the password back to the original by supplying the new password as current and the original 
password as new. Verify the response status is 200 and verify that login with the ORIGINAL password succeeds again.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_update_password_me():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Update password to a new password
    new_password = f"newpassword_{uuid.uuid4().hex[:8]}"
    update_response1 = requests.patch(
        f"{BASE_URL}/api/v1/users/me/password",
        headers=headers,
        json={"current_password": "password123", "new_password": new_password}
    )
    
    # Verify first update response
    assert update_response1.status_code == 200
    response_json1 = update_response1.json()
    assert response_json1["message"] == "Password updated successfully"
    
    # Verify login with NEW password works
    login_new_password = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": new_password}
    )
    assert login_new_password.status_code == 200, "Login with new password should succeed"
    new_access_token = login_new_password.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_access_token}"}
    
    # Revert password back to original (use new token since password changed)
    update_response2 = requests.patch(
        f"{BASE_URL}/api/v1/users/me/password",
        headers=new_headers,
        json={"current_password": new_password, "new_password": "password123"}
    )
    
    # Verify second update response
    assert update_response2.status_code == 200
    response_json2 = update_response2.json()
    assert response_json2["message"] == "Password updated successfully"
    
    # Verify login with ORIGINAL password works again
    login_original_password = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_original_password.status_code == 200, "Login with original password should succeed after revert"
