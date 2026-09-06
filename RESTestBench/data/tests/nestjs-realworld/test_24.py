"""
Golden test for Requirement 25: Articles ordered by created date DESC
"""

import requests
import pytest
import time

BASE_URL = "http://localhost:3000"


def test_articles_ordered_by_created_desc():
    """
    Test that articles are returned in descending order by created date.
    
    Mutants:
    - Line 49: 'ASC' instead of 'DESC' - wrong order
    - Line 49: comment out orderBy - undefined order
    """
    
    # Create user
    user_data = {
        "user": {
            "username": "orderuser1",
            "email": "orderuser1@test.com",
            "password": "pass123"
        }
    }
    user_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert user_response.status_code in [200, 201]
    token = user_response.json()["user"]["token"]
    headers = {"Authorization": f"Token {token}"}
    
    # Create first article
    article1_data = {
        "article": {
            "title": "First Article Order",
            "description": "Created first",
            "body": "Body first",
            "tagList": ["first"]
        }
    }
    article1_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article1_data,
        headers=headers
    )
    assert article1_response.status_code in [200, 201]
    
    # Use 1.1 second delay to ensure different timestamps (MySQL precision is 1 second)
    time.sleep(1.1)
    
    # Create second article
    article2_data = {
        "article": {
            "title": "Second Article Order",
            "description": "Created second",
            "body": "Body second",
            "tagList": ["second"]
        }
    }
    article2_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article2_data,
        headers=headers
    )
    assert article2_response.status_code in [200, 201]
    
    # Another delay
    time.sleep(1.1)
    
    # Create third article
    article3_data = {
        "article": {
            "title": "Third Article Order",
            "description": "Created third",
            "body": "Body third",
            "tagList": ["third"]
        }
    }
    article3_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article3_data,
        headers=headers
    )
    assert article3_response.status_code in [200, 201]
    
    # Get articles filtered by author to only get our test articles
    list_response = requests.get(f"{BASE_URL}/api/articles?author=orderuser1")
    assert list_response.status_code == 200
    articles = list_response.json()["articles"]
    
    # Should have exactly 3 articles
    assert len(articles) == 3, f"Expected 3 articles, got {len(articles)}"
    
    # First article should be "Third Article Order" (newest)
    assert articles[0]["title"] == "Third Article Order", \
        f"Expected 'Third Article Order' first (newest), got '{articles[0]['title']}'"
    
    # Second article should be "Second Article Order"
    assert articles[1]["title"] == "Second Article Order", \
        f"Expected 'Second Article Order' second, got '{articles[1]['title']}'"
    
    # Third article should be "First Article Order" (oldest)
    assert articles[2]["title"] == "First Article Order", \
        f"Expected 'First Article Order' third (oldest), got '{articles[2]['title']}'"
