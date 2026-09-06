"""
Golden test for Requirement 22: Article title and description are stored correctly
"""

import requests
import pytest

BASE_URL = "http://localhost:3000"


def test_article_title_and_description_stored():
    """
    Test that article title and description are correctly stored and retrieved.
    
    Mutants:
    - Line 171: description = 'wrong' - wrong description stored
    - Line 170: title = 'wrong' - wrong title stored
    """
    
    # Create user
    user_data = {
        "user": {
            "username": "bodyuser1",
            "email": "bodyuser1@test.com",
            "password": "pass123"
        }
    }
    user_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert user_response.status_code in [200, 201]
    token = user_response.json()["user"]["token"]
    headers = {"Authorization": f"Token {token}"}
    
    # Create article with specific title and description
    article_data = {
        "article": {
            "title": "Body Test Article",
            "description": "Test description content",
            "body": "This is the complete article body with some special content @#$%",
            "tagList": ["test"]
        }
    }
    article_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article_data,
        headers=headers
    )
    assert article_response.status_code in [200, 201]
    slug = article_response.json()["slug"]
    
    # GET the article
    get_response = requests.get(f"{BASE_URL}/api/articles/{slug}")
    assert get_response.status_code == 200
    article = get_response.json()["article"]
    
    # Verify title is correct
    assert article["title"] == "Body Test Article", \
        f"Expected title='Body Test Article', got '{article['title']}'"
    
    # Verify description is correct
    assert article["description"] == "Test description content", \
        f"Expected description='Test description content', got '{article['description']}'"
