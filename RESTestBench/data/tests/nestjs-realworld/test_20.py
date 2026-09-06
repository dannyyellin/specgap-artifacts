"""
Golden test for Requirement 21: Article slugs are unique with random suffix
"""

import requests
import pytest

BASE_URL = "http://localhost:3000"


def test_article_slugs_are_unique():
    """
    Test that articles with same title get different slugs due to random suffix.
    
    Mutants:
    - Line 202: remove random suffix - slugs will be identical
    - Line 202: use '-fixed' suffix - slugs will be identical
    """
    
    # Create user
    user_data = {
        "user": {
            "username": "sluguser1",
            "email": "sluguser1@test.com",
            "password": "pass123"
        }
    }
    user_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert user_response.status_code in [200, 201]
    token = user_response.json()["user"]["token"]
    headers = {"Authorization": f"Token {token}"}
    
    # Create first article with specific title
    article1_data = {
        "article": {
            "title": "Duplicate Title Article",
            "description": "First article",
            "body": "Body 1",
            "tagList": ["test"]
        }
    }
    article1_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article1_data,
        headers=headers
    )
    assert article1_response.status_code in [200, 201]
    slug1 = article1_response.json()["slug"]
    
    # Create second article with SAME title
    article2_data = {
        "article": {
            "title": "Duplicate Title Article",
            "description": "Second article",
            "body": "Body 2",
            "tagList": ["test"]
        }
    }
    article2_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article2_data,
        headers=headers
    )
    assert article2_response.status_code in [200, 201]
    slug2 = article2_response.json()["slug"]
    
    # Slugs should both start with the same base
    assert slug1.startswith("duplicate-title-article-"), \
        f"Slug1 should start with 'duplicate-title-article-', got '{slug1}'"
    assert slug2.startswith("duplicate-title-article-"), \
        f"Slug2 should start with 'duplicate-title-article-', got '{slug2}'"
    
    # Slugs should be DIFFERENT (random suffix)
    assert slug1 != slug2, \
        f"Slugs should be different due to random suffix, but both are '{slug1}'"
