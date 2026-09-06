"""
Golden test for Requirement 18: Article creation correctly associates article with author
"""

import requests
import pytest

BASE_URL = "http://localhost:3000"


def test_article_author_relationship():
    """
    Test that creating an article correctly associates it with the author,
    so filtering by author returns only that author's articles.
    """
    
    # Create user1
    user1_data = {
        "user": {
            "username": "articleauthor1",
            "email": "articleauthor1@test.com",
            "password": "pass123"
        }
    }
    user1_response = requests.post(f"{BASE_URL}/api/users", json=user1_data)
    assert user1_response.status_code in [200, 201]
    user1_token = user1_response.json()["user"]["token"]
    user1_headers = {"Authorization": f"Token {user1_token}"}
    
    # Create user2
    user2_data = {
        "user": {
            "username": "articleauthor2",
            "email": "articleauthor2@test.com",
            "password": "pass123"
        }
    }
    user2_response = requests.post(f"{BASE_URL}/api/users", json=user2_data)
    assert user2_response.status_code in [200, 201]
    user2_token = user2_response.json()["user"]["token"]
    user2_headers = {"Authorization": f"Token {user2_token}"}
    
    # User1 creates article
    article1_data = {
        "article": {
            "title": "User1 Article",
            "description": "Article by user1",
            "body": "Body of user1 article",
            "tagList": ["user1tag"]
        }
    }
    article1_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article1_data,
        headers=user1_headers
    )
    assert article1_response.status_code in [200, 201]
    
    # User2 creates article
    article2_data = {
        "article": {
            "title": "User2 Article",
            "description": "Article by user2",
            "body": "Body of user2 article",
            "tagList": ["user2tag"]
        }
    }
    article2_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article2_data,
        headers=user2_headers
    )
    assert article2_response.status_code in [200, 201]
    
    # GET articles filtered by author=articleauthor1
    filter_user1_response = requests.get(
        f"{BASE_URL}/api/articles?author=articleauthor1"
    )
    assert filter_user1_response.status_code == 200
    user1_articles = filter_user1_response.json()
    
    assert user1_articles["articlesCount"] == 1, f"Expected 1 article for author1, got {user1_articles['articlesCount']}"
    assert user1_articles["articles"][0]["title"] == "User1 Article"
    
    # GET articles filtered by author=articleauthor2
    filter_user2_response = requests.get(
        f"{BASE_URL}/api/articles?author=articleauthor2"
    )
    assert filter_user2_response.status_code == 200
    user2_articles = filter_user2_response.json()
    
    assert user2_articles["articlesCount"] == 1, f"Expected 1 article for author2, got {user2_articles['articlesCount']}"
    assert user2_articles["articles"][0]["title"] == "User2 Article"
