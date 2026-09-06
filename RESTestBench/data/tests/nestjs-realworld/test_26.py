"""
Golden test for Requirement 27: Multiple comments per article with unique IDs
"""

import requests
import pytest

BASE_URL = "http://localhost:3000"


def test_multiple_comments_with_unique_ids():
    """
    Test that multiple comments can be added to an article with unique IDs.
    
    Mutants:
    - Line 107: comment out 'article.comments.push(comment)' - comments not added
    - Line 105: 'comment.body = "overwritten"' - wrong body text
    """
    
    # Create user
    user_data = {
        "user": {
            "username": "multicommentuser1",
            "email": "multicommentuser1@test.com",
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
            "title": "Multi Comment Article",
            "description": "Article for multiple comments",
            "body": "Body content",
            "tagList": ["comments"]
        }
    }
    article_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article_data,
        headers=headers
    )
    assert article_response.status_code in [200, 201]
    slug = article_response.json()["slug"]
    
    # Add first comment
    comment1_data = {"comment": {"body": "First comment"}}
    comment1_response = requests.post(
        f"{BASE_URL}/api/articles/{slug}/comments",
        json=comment1_data,
        headers=headers
    )
    assert comment1_response.status_code in [200, 201]
    
    # Add second comment
    comment2_data = {"comment": {"body": "Second comment"}}
    comment2_response = requests.post(
        f"{BASE_URL}/api/articles/{slug}/comments",
        json=comment2_data,
        headers=headers
    )
    assert comment2_response.status_code in [200, 201]
    
    # Add third comment
    comment3_data = {"comment": {"body": "Third comment"}}
    comment3_response = requests.post(
        f"{BASE_URL}/api/articles/{slug}/comments",
        json=comment3_data,
        headers=headers
    )
    assert comment3_response.status_code in [200, 201]
    
    # Get all comments for the article
    comments_response = requests.get(f"{BASE_URL}/api/articles/{slug}/comments")
    assert comments_response.status_code == 200
    comments = comments_response.json()["comments"]
    
    # Should have 3 comments
    assert len(comments) == 3, f"Expected 3 comments, got {len(comments)}"
    
    # Verify unique IDs
    ids = [c["id"] for c in comments]
    assert len(ids) == len(set(ids)), f"Comment IDs should be unique, got {ids}"
    
    # Verify comment bodies are preserved
    bodies = [c["body"] for c in comments]
    assert "First comment" in bodies, "First comment body not found"
    assert "Second comment" in bodies, "Second comment body not found"
    assert "Third comment" in bodies, "Third comment body not found"
