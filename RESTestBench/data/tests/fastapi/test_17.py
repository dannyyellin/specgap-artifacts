"""
Scenario 17: Create a new user with a generated email and initial password. Authenticate as the 
superuser (admin@example.com / password123). Using the superuser access token, request the password-recovery 
HTML content for the created user's email. Then submit the password reset request as user using the extracted 
reset token from the HTML a new password. Verify the password reset response has HTTP 200 and the response 
JSON is exactly {"message": "Password updated successfully"}.
"""
import requests
import uuid
import re

BASE_URL = "http://localhost:8000"


def test_reset_password():
    # Register a new user
    user_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    user_password = "password123"
    register_response = requests.post(
        f"{BASE_URL}/api/v1/users/signup",
        json={"email": user_email, "password": user_password}
    )
    assert register_response.status_code == 200
    
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    admin_access_token = login_response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_access_token}"}
    
    # Get password recovery HTML content
    html_response = requests.post(
        f"{BASE_URL}/api/v1/password-recovery-html-content/{user_email}",
        headers=admin_headers
    )
    assert html_response.status_code == 200
    
    # Extract token from HTML content (response is HTML, not JSON)
    html_content = html_response.text
    # Token is in the HTML link
    token_match = re.search(r'token=([^&"\s]+)', html_content)
    assert token_match is not None
    reset_token = token_match.group(1)
    
    # Reset password using the token
    new_password = "newpassword123"
    reset_response = requests.post(
        f"{BASE_URL}/api/v1/reset-password/",
        json={"token": reset_token, "new_password": new_password}
    )
    
    # Verify response
    assert reset_response.status_code == 200
    response_json = reset_response.json()
    assert response_json == {"message": "Password updated successfully"}
    
    # Verify login with new password works
    login_with_new_password = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": user_email, "password": new_password}
    )
    assert login_with_new_password.status_code == 200, "Login with new password should succeed"
