"""
Golden test for Requirement 20: Article updated timestamp changes on update
"""

import requests
import pytest
import time

BASE_URL = "http://localhost:3000"


def test_article_timestamp_update():
    """
    Test that updating an article changes the 'updated' timestamp but preserves the 'created' timestamp.
    """
    
    # Create user
    user_data = {
        "user": {
            "username": "timestampuser1",
            "email": "timestampuser1@test.com",
            "password": "pass123"
        }
    }
    user_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert user_response.status_code in [200, 201]
    token = user_response.json()["user"]["token"]
    headers = {"Authorization": f"Token {token}"}
    
    # Create article
    article_data = {
        "article": {
            "title": "Timestamp Test Article",
            "description": "Test description",
            "body": "Test body",
            "tagList": ["timestamp"]
        }
    }
    article_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article_data,
        headers=headers
    )
    assert article_response.status_code in [200, 201]
    created_article = article_response.json()
    slug = created_article["slug"]
    original_created = created_article["created"]
    original_updated = created_article["updated"]
    
    # Wait a brief moment to ensure timestamp difference is detectable
    time.sleep(1.5)
    
    # Update the article
    update_data = {
        "article": {
            "title": "Updated Timestamp Article",
            "description": "Updated description"
        }
    }
    update_response = requests.put(
        f"{BASE_URL}/api/articles/{slug}",
        json=update_data,
        headers=headers
    )
    assert update_response.status_code == 200
    
    # GET the article to verify timestamps
    get_response = requests.get(f"{BASE_URL}/api/articles/{slug}")
    assert get_response.status_code == 200
    updated_article = get_response.json()["article"]
    
    new_created = updated_article["created"]
    new_updated = updated_article["updated"]
    
    # Verify 'created' timestamp is unchanged
    assert new_created == original_created, f"Created timestamp should not change. Original: {original_created}, New: {new_created}"
    
    # Verify 'updated' timestamp has changed (is different and newer)
    assert new_updated != original_updated, f"Updated timestamp should change after update. Original: {original_updated}, New: {new_updated}"
    
    # Parse and compare timestamps to ensure updated is newer
    # The timestamps are in ISO format, so string comparison works for this
    assert new_updated > original_updated, f"New updated timestamp should be newer. Original: {original_updated}, New: {new_updated}"
