"""
Golden test for Requirement 16: Profile returns correct following status based on follow relationship
"""

import requests
import pytest

BASE_URL = "http://localhost:3000"


def test_profile_following_status_reflects_relationship():
    """
    Test that GET /api/profiles/{username} returns correct following status
    based on whether the authenticated user follows the target user.
    """
    
    # Create user1 (the viewer)
    user1_data = {
        "user": {
            "username": "profileviewer1",
            "email": "profileviewer1@test.com",
            "password": "pass123"
        }
    }
    user1_response = requests.post(f"{BASE_URL}/api/users", json=user1_data)
    assert user1_response.status_code in [200, 201]
    user1_token = user1_response.json()["user"]["token"]
    user1_headers = {"Authorization": f"Token {user1_token}"}
    
    # Create user2 (the target profile)
    user2_data = {
        "user": {
            "username": "profiletarget1",
            "email": "profiletarget1@test.com",
            "password": "pass123"
        }
    }
    user2_response = requests.post(f"{BASE_URL}/api/users", json=user2_data)
    assert user2_response.status_code in [200, 201]
    
    # GET profile of user2 using user1's token - should show following: false
    profile_response1 = requests.get(
        f"{BASE_URL}/api/profiles/profiletarget1",
        headers=user1_headers
    )
    assert profile_response1.status_code == 200
    profile1 = profile_response1.json()["profile"]
    assert profile1["following"] == False, f"Expected following=False before follow, got {profile1['following']}"
    
    # User1 follows user2
    follow_response = requests.post(
        f"{BASE_URL}/api/profiles/profiletarget1/follow",
        headers=user1_headers
    )
    assert follow_response.status_code in [200, 201]
    
    # GET profile of user2 again - should show following: true
    profile_response2 = requests.get(
        f"{BASE_URL}/api/profiles/profiletarget1",
        headers=user1_headers
    )
    assert profile_response2.status_code == 200
    profile2 = profile_response2.json()["profile"]
    assert profile2["following"] == True, f"Expected following=True after follow, got {profile2['following']}"
    # Verify username is correct (catches username mutation)
    assert profile2["username"] == "profiletarget1", f"Expected username 'profiletarget1', got {profile2['username']}"
    
    # User1 unfollows user2
    unfollow_response = requests.delete(
        f"{BASE_URL}/api/profiles/profiletarget1/follow",
        headers=user1_headers
    )
    assert unfollow_response.status_code == 200
    
    # GET profile of user2 again - should show following: false again
    profile_response3 = requests.get(
        f"{BASE_URL}/api/profiles/profiletarget1",
        headers=user1_headers
    )
    assert profile_response3.status_code == 200
    profile3 = profile_response3.json()["profile"]
    assert profile3["following"] == False, f"Expected following=False after unfollow, got {profile3['following']}"
