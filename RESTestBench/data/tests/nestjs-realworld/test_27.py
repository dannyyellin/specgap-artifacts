"""
Golden test for Requirement 28: Empty feed for user with no follows
"""

import requests
import pytest

BASE_URL = "http://localhost:3000"


def test_empty_feed_when_no_follows():
    """
    Test that feed is empty when user follows nobody.
    
    Mutants:
    - Line 69: 'if (false)' - skips empty check, might error
    - Line 70: 'articlesCount: 99' - wrong count for empty feed
    """
    
    # Create user1 who will check feed (follows nobody)
    user1_data = {
        "user": {
            "username": "emptyfeeduser1",
            "email": "emptyfeeduser1@test.com",
            "password": "pass123"
        }
    }
    user1_response = requests.post(f"{BASE_URL}/api/users", json=user1_data)
    assert user1_response.status_code in [200, 201]
    user1_token = user1_response.json()["user"]["token"]
    user1_headers = {"Authorization": f"Token {user1_token}"}
    
    # Create user2 who will create an article
    user2_data = {
        "user": {
            "username": "emptyfeedauthor1",
            "email": "emptyfeedauthor1@test.com",
            "password": "pass123"
        }
    }
    user2_response = requests.post(f"{BASE_URL}/api/users", json=user2_data)
    assert user2_response.status_code in [200, 201]
    user2_token = user2_response.json()["user"]["token"]
    user2_headers = {"Authorization": f"Token {user2_token}"}
    
    # User2 creates an article
    article_data = {
        "article": {
            "title": "Article by User2",
            "description": "This should NOT appear in user1's feed",
            "body": "Body content",
            "tagList": ["test"]
        }
    }
    article_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article_data,
        headers=user2_headers
    )
    assert article_response.status_code in [200, 201]
    
    # User1 (who follows nobody) gets feed
    feed_response = requests.get(
        f"{BASE_URL}/api/articles/feed",
        headers=user1_headers
    )
    assert feed_response.status_code == 200
    feed = feed_response.json()
    
    # Feed should be empty
    assert feed["articlesCount"] == 0, \
        f"Expected articlesCount=0 for user with no follows, got {feed['articlesCount']}"
    assert len(feed["articles"]) == 0, \
        f"Expected empty articles array, got {len(feed['articles'])} articles"
