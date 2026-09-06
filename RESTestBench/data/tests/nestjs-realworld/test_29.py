"""
Golden test for Requirement 29: User deletion blocked by FK constraint (no cascade delete on articles)
"""

import requests
import pytest

BASE_URL = "http://localhost:3000"


def test_user_delete_blocked_by_articles():
    """
    Test that user deletion fails when user has articles due to FK constraint.
    This proves no CASCADE DELETE is configured on articles.
    """
    
    # Create user1 (article author)
    user1_data = {
        "user": {
            "username": "orphanauthor1",
            "email": "orphanauthor1@test.com",
            "password": "pass123"
        }
    }
    user1_response = requests.post(f"{BASE_URL}/api/users", json=user1_data)
    assert user1_response.status_code in [200, 201], f"Failed to create user1: {user1_response.text}"
    token1 = user1_response.json()["user"]["token"]
    headers1 = {"Authorization": f"Token {token1}"}
    
    # User1 creates an article
    article_data = {
        "article": {
            "title": "Orphan Article Test",
            "description": "This article blocks user deletion",
            "body": "Testing FK constraint",
            "tagList": []
        }
    }
    article_response = requests.post(f"{BASE_URL}/api/articles", json=article_data, headers=headers1)
    assert article_response.status_code in [200, 201], f"Failed to create article: {article_response.text}"
    slug = article_response.json()["slug"]
    
    # Verify article exists via list endpoint (includes author)
    list_response = requests.get(f"{BASE_URL}/api/articles")
    assert list_response.status_code == 200
    articles = list_response.json()["articles"]
    our_article = next((a for a in articles if a["slug"] == slug), None)
    assert our_article is not None, "Article should be in list"
    assert our_article["author"]["username"] == "orphanauthor1", f"Author should be orphanauthor1"
    
    # Try to delete user1 - this should FAIL with FK constraint error (500)
    delete_response = requests.delete(f"{BASE_URL}/api/users/orphanauthor1@test.com")
    # User delete should fail because article references this user
    assert delete_response.status_code == 500, f"User delete should fail with FK constraint, got: {delete_response.status_code}"
    
    # Verify article still exists
    list_response2 = requests.get(f"{BASE_URL}/api/articles")
    assert list_response2.status_code == 200
    articles2 = list_response2.json()["articles"]
    our_article2 = next((a for a in articles2 if a["slug"] == slug), None)
    assert our_article2 is not None, "Article should still exist after failed user delete"
