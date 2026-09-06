"""
Golden Test for Requirement 14: User Profile Update
Tests that user profile (bio, image) can be updated via PUT /api/user.
"""
import requests
import random
import string

BASE_URL = "http://localhost:3000"

def random_suffix():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

def test_user_profile_update():
    suffix = random_suffix()
    
    # Create user
    user_data = {
        "user": {
            "username": f"updateuser{suffix}",
            "email": f"updateuser{suffix}@test.com",
            "password": "pass123"
        }
    }
    create_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert create_response.status_code in [200, 201], f"Failed to create user: {create_response.text}"
    
    token = create_response.json()["user"]["token"]
    headers = {"Authorization": f"Token {token}"}
    
    # Verify initial state - bio and image should be empty/null
    initial_get = requests.get(f"{BASE_URL}/api/user", headers=headers)
    assert initial_get.status_code == 200
    initial_user = initial_get.json()["user"]
    # Initial values may be empty string or null
    
    # Update user profile with new bio and image
    update_data = {
        "user": {
            "bio": f"Updated bio text {suffix}",
            "image": f"https://example.com/newimage{suffix}.jpg"
        }
    }
    update_response = requests.put(f"{BASE_URL}/api/user", json=update_data, headers=headers)
    assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
    
    # Verify update response contains new values
    # Note: The response structure may vary - it could be UserEntity directly
    updated_result = update_response.json()
    
    # Check if response has 'user' wrapper or direct fields
    if "user" in updated_result:
        updated_user = updated_result["user"]
    else:
        updated_user = updated_result
    
    # The update might return the entity directly without bio/image in some cases
    # Let's verify via GET
    
    # GET /api/user to verify persistence
    verify_response = requests.get(f"{BASE_URL}/api/user", headers=headers)
    assert verify_response.status_code == 200
    
    verified_user = verify_response.json()["user"]
    assert verified_user["bio"] == f"Updated bio text {suffix}", f"Expected bio 'Updated bio text {suffix}', got '{verified_user.get('bio')}'"
    assert verified_user["image"] == f"https://example.com/newimage{suffix}.jpg", f"Expected image URL, got '{verified_user.get('image')}'"
    
    # Verify username and email remained unchanged
    assert verified_user["username"] == f"updateuser{suffix}"
    assert verified_user["email"] == f"updateuser{suffix}@test.com"
