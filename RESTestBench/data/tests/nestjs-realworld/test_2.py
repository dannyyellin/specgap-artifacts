"""
Scenario 2: Verify following a user updates the profile following status correctly and prevents self-following.
Create two users: user1 (username: 'follower1', email: 'follower1@test.com', password: 'pass123') and 
user2 (username: 'followee1', email: 'followee1@test.com', password: 'pass123'). Using user1's token, 
follow user2 by POST to /api/profiles/followee1/follow. Verify the response status is 200. Verify the 
response body profile has 'following' equal to true and 'username' equal to 'followee1'. Then GET the 
profile /api/profiles/followee1 with user1's token and verify 'following' is true. Next, using user1's 
token, attempt to follow themselves by POST to /api/profiles/follower1/follow. Verify this returns 
status 400 with message containing 'cannot be equal'.
"""
import requests
import random
import string

BASE_URL = "http://localhost:3000"

def random_suffix():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))


def test_follow_user_and_prevent_self_follow():
    suffix = random_suffix()
    
    # Create user1 (follower)
    user1_data = {
        "user": {
            "username": f"follower{suffix}",
            "email": f"follower{suffix}@test.com",
            "password": "pass123"
        }
    }
    response1 = requests.post(f"{BASE_URL}/api/users", json=user1_data)
    assert response1.status_code == 201, f"Expected 201, got {response1.status_code}: {response1.text}"
    user1_token = response1.json()["user"]["token"]
    user1_username = f"follower{suffix}"
    user1_headers = {"Authorization": f"Token {user1_token}"}
    
    # Create user2 (followee)
    user2_data = {
        "user": {
            "username": f"followee{suffix}",
            "email": f"followee{suffix}@test.com",
            "password": "pass123"
        }
    }
    response2 = requests.post(f"{BASE_URL}/api/users", json=user2_data)
    assert response2.status_code == 201, f"Expected 201, got {response2.status_code}: {response2.text}"
    user2_username = f"followee{suffix}"
    
    # User1 follows user2
    follow_response = requests.post(
        f"{BASE_URL}/api/profiles/{user2_username}/follow",
        headers=user1_headers
    )
    assert follow_response.status_code in [200, 201], f"Expected 200/201, got {follow_response.status_code}: {follow_response.text}"
    
    follow_json = follow_response.json()
    assert "profile" in follow_json, "Response should contain 'profile' object"
    profile = follow_json["profile"]
    assert profile["following"] == True, f"Expected following to be True, got {profile['following']}"
    assert profile["username"] == user2_username, f"Expected username '{user2_username}', got {profile['username']}"
    
    # GET profile to verify following status persisted
    get_profile_response = requests.get(
        f"{BASE_URL}/api/profiles/{user2_username}",
        headers=user1_headers
    )
    assert get_profile_response.status_code == 200, f"Expected 200, got {get_profile_response.status_code}"
    
    get_profile_json = get_profile_response.json()
    assert get_profile_json["profile"]["following"] == True, "Following should be True after follow"
    
    # User1 attempts to follow themselves (should fail)
    self_follow_response = requests.post(
        f"{BASE_URL}/api/profiles/{user1_username}/follow",
        headers=user1_headers
    )
    assert self_follow_response.status_code == 400, f"Expected 400 for self-follow, got {self_follow_response.status_code}"
    assert "cannot be equal" in self_follow_response.text.lower(), f"Expected 'cannot be equal' in response: {self_follow_response.text}"
