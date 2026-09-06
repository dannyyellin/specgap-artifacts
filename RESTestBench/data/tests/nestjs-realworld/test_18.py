"""
Golden test for Requirement 19: Article tagList is correctly stored and persisted
"""

import requests
import pytest

BASE_URL = "http://localhost:3000"


def test_article_taglist_persistence():
    """
    Test that article tagList is correctly stored as a simple-array and can be retrieved.
    """
    
    # Create user
    user_data = {
        "user": {
            "username": "taglistuser1",
            "email": "taglistuser1@test.com",
            "password": "pass123"
        }
    }
    user_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert user_response.status_code in [200, 201]
    token = user_response.json()["user"]["token"]
    headers = {"Authorization": f"Token {token}"}
    
    # Create article with multiple tags
    article_data = {
        "article": {
            "title": "Multi Tag Article",
            "description": "Article with multiple tags",
            "body": "Body text",
            "tagList": ["tag1", "tag2", "tag3"]
        }
    }
    article_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article_data,
        headers=headers
    )
    assert article_response.status_code in [200, 201]
    created_article = article_response.json()
    slug1 = created_article["slug"]
    
    # Verify tagList in creation response
    assert "tagList" in created_article, "Response should contain tagList"
    assert created_article["tagList"] == ["tag1", "tag2", "tag3"], f"Expected ['tag1', 'tag2', 'tag3'], got {created_article['tagList']}"
    
    # GET the article and verify tagList persisted
    get_response = requests.get(f"{BASE_URL}/api/articles/{slug1}")
    assert get_response.status_code == 200
    retrieved_article = get_response.json()["article"]
    
    assert retrieved_article["tagList"] == ["tag1", "tag2", "tag3"], f"Expected ['tag1', 'tag2', 'tag3'] after GET, got {retrieved_article['tagList']}"
    
    # Create article with empty tagList
    article2_data = {
        "article": {
            "title": "No Tag Article",
            "description": "Article with no tags",
            "body": "Body text"
            # No tagList provided - should default to []
        }
    }
    article2_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article2_data,
        headers=headers
    )
    assert article2_response.status_code in [200, 201]
    created_article2 = article2_response.json()
    slug2 = created_article2["slug"]
    
    # GET the article and verify tagList is empty array
    get_response2 = requests.get(f"{BASE_URL}/api/articles/{slug2}")
    assert get_response2.status_code == 200
    retrieved_article2 = get_response2.json()["article"]
    
    assert retrieved_article2["tagList"] == [] or retrieved_article2["tagList"] == [""], f"Expected empty tagList, got {retrieved_article2['tagList']}"
