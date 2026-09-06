"""
Scenario 10: Verify unfollow removes follow relationship and updates profile following status.
Create user1 (username: 'unfollower1', email: 'unfollower1@test.com', password: 'pass123') and 
user2 (username: 'unfollowee1', email: 'unfollowee1@test.com', password: 'pass123'). User1 
follows user2. Verify following is true. User1 unfollows user2 via DELETE 
/api/profiles/unfollowee1/follow. Verify response status is 200. Verify response profile has 
'following' equal to false. GET profile of user2 using user1's token. Verify 'following' is 
false. Verify user1 cannot unfollow themselves (should return 400).
"""
import requests

BASE_URL = "http://localhost:3000"


def test_unfollow_user_and_prevent_self_unfollow():
    # Create user1 (unfollower)
    user1_data = {
        "user": {
            "username": "unfollower1",
            "email": "unfollower1@test.com",
            "password": "pass123"
        }
    }
    response1 = requests.post(f"{BASE_URL}/api/users", json=user1_data)
    assert response1.status_code == 201, f"Expected 201, got {response1.status_code}: {response1.text}"
    user1_token = response1.json()["user"]["token"]
    user1_headers = {"Authorization": f"Token {user1_token}"}
    
    # Create user2 (unfollowee)
    user2_data = {
        "user": {
            "username": "unfollowee1",
            "email": "unfollowee1@test.com",
            "password": "pass123"
        }
    }
    response2 = requests.post(f"{BASE_URL}/api/users", json=user2_data)
    assert response2.status_code == 201, f"Expected 201, got {response2.status_code}: {response2.text}"
    
    # User1 follows user2
    follow_response = requests.post(
        f"{BASE_URL}/api/profiles/unfollowee1/follow",
        headers=user1_headers
    )
    assert follow_response.status_code in [200, 201]
    assert follow_response.json()["profile"]["following"] == True, "Following should be True after follow"
    
    # User1 unfollows user2
    unfollow_response = requests.delete(
        f"{BASE_URL}/api/profiles/unfollowee1/follow",
        headers=user1_headers
    )
    assert unfollow_response.status_code == 200, f"Expected 200, got {unfollow_response.status_code}: {unfollow_response.text}"
    
    unfollow_profile = unfollow_response.json()["profile"]
    assert unfollow_profile["following"] == False, f"Expected following to be False after unfollow, got {unfollow_profile['following']}"
    
    # GET profile to verify unfollow persisted
    get_profile_response = requests.get(
        f"{BASE_URL}/api/profiles/unfollowee1",
        headers=user1_headers
    )
    assert get_profile_response.status_code == 200
    
    get_profile_json = get_profile_response.json()
    assert get_profile_json["profile"]["following"] == False, "Following should be False after unfollow"
    
    # User1 attempts to unfollow themselves (should fail)
    self_unfollow_response = requests.delete(
        f"{BASE_URL}/api/profiles/unfollower1/follow",
        headers=user1_headers
    )
    assert self_unfollow_response.status_code == 400, f"Expected 400 for self-unfollow, got {self_unfollow_response.status_code}"
    assert "cannot be equal" in self_unfollow_response.text.lower(), f"Expected 'cannot be equal' in response: {self_unfollow_response.text}"
