"""
Golden test for Requirement 23: Profile returns correct bio and image
"""

import requests
import pytest

BASE_URL = "http://localhost:3000"


def test_profile_returns_bio_and_image():
    """
    Test that profile endpoint returns correct bio and image fields.
    
    Mutants:
    - Line 36: bio = 'wrong' - wrong bio returned
    - Line 37: image = 'wrong' - wrong image returned
    """
    
    # Create user
    user_data = {
        "user": {
            "username": "profilebiouser1",
            "email": "profilebiouser1@test.com",
            "password": "pass123"
        }
    }
    user_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert user_response.status_code in [200, 201]
    token = user_response.json()["user"]["token"]
    headers = {"Authorization": f"Token {token}"}
    
    # Update user profile with bio and image
    update_data = {
        "user": {
            "bio": "This is my bio text",
            "image": "https://example.com/avatar.jpg"
        }
    }
    update_response = requests.put(
        f"{BASE_URL}/api/user",
        json=update_data,
        headers=headers
    )
    assert update_response.status_code == 200
    
    # GET the profile
    profile_response = requests.get(
        f"{BASE_URL}/api/profiles/profilebiouser1",
        headers=headers
    )
    assert profile_response.status_code == 200
    profile = profile_response.json()["profile"]
    
    # Verify username
    assert profile["username"] == "profilebiouser1", \
        f"Expected username='profilebiouser1', got '{profile['username']}'"
    
    # Verify bio
    assert profile["bio"] == "This is my bio text", \
        f"Expected bio='This is my bio text', got '{profile['bio']}'"
    
    # Verify image
    assert profile["image"] == "https://example.com/avatar.jpg", \
        f"Expected image='https://example.com/avatar.jpg', got '{profile['image']}'"
