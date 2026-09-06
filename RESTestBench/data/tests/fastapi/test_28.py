"""
Scenario 28: Authenticate as the superuser (use admin@example.com / password123) to obtain an access token. 
Using that superuser access token, create two distinct users via the public create-user API (each with a unique 
email and password). Store the returned user IDs and emails. Then, using the same superuser access token, 
retrieve the list of all users. Verify the response status is 200. Verify the response JSON contains a top-level 
'data' collection and a top-level 'count' key. Verify that both created users appear in the 'data' collection 
by checking that their emails are present. Verify that for each created user, the email in the list matches 
the email used during creation.
"""
import requests
import uuid

BASE_URL = "http://localhost:8000"


def test_retrieve_users():
    # Authenticate as superuser
    login_response = requests.post(
        f"{BASE_URL}/api/v1/login/access-token",
        data={"username": "admin@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Create first user
    user1_email = f"user1_{uuid.uuid4().hex[:8]}@example.com"
    user1_password = "password123"
    create_response1 = requests.post(
        f"{BASE_URL}/api/v1/users/",
        headers=headers,
        json={"email": user1_email, "password": user1_password}
    )
    assert create_response1.status_code == 200
    user1_id = create_response1.json()["id"]
    
    # Create second user
    user2_email = f"user2_{uuid.uuid4().hex[:8]}@example.com"
    user2_password = "password123"
    create_response2 = requests.post(
        f"{BASE_URL}/api/v1/users/",
        headers=headers,
        json={"email": user2_email, "password": user2_password}
    )
    assert create_response2.status_code == 200
    user2_id = create_response2.json()["id"]
    
    # Retrieve all users
    read_response = requests.get(
        f"{BASE_URL}/api/v1/users/",
        headers=headers
    )
    
    # Verify response structure
    assert read_response.status_code == 200
    response_json = read_response.json()
    assert "data" in response_json
    assert "count" in response_json
    
    # Verify created users are in the response with correct emails
    user_emails_in_response = [user["email"] for user in response_json["data"]]
    assert user1_email in user_emails_in_response, f"User 1 email {user1_email} not found in response"
    assert user2_email in user_emails_in_response, f"User 2 email {user2_email} not found in response"
    
    # Verify the emails match what was created
    for user in response_json["data"]:
        if user["id"] == user1_id:
            assert user["email"] == user1_email
        if user["id"] == user2_id:
            assert user["email"] == user2_email
