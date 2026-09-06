"""
Golden test for Requirement 24: Feed pagination with limit and offset
"""

import requests
import pytest
import time

BASE_URL = "http://localhost:3000"


def test_feed_pagination_limit_and_offset():
    """
    Test that feed respects limit and offset parameters for pagination.
    
    Mutants:
    - Line 83: articles.slice(0) - ignores limit
    - Line 87: articles.slice(limit) - ignores offset, starts from limit
    """
    
    # Create author who will write articles
    author_data = {
        "user": {
            "username": "feedpagauthor1",
            "email": "feedpagauthor1@test.com",
            "password": "pass123"
        }
    }
    author_response = requests.post(f"{BASE_URL}/api/users", json=author_data)
    assert author_response.status_code in [200, 201]
    author_token = author_response.json()["user"]["token"]
    author_headers = {"Authorization": f"Token {author_token}"}
    
    # Create 5 articles with small delay to ensure ordering
    article_titles = []
    for i in range(5):
        article_data = {
            "article": {
                "title": f"Feed Pagination Article {i+1}",
                "description": f"Description {i+1}",
                "body": f"Body of article {i+1}",
                "tagList": ["feed"]
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/articles",
            json=article_data,
            headers=author_headers
        )
        assert response.status_code in [200, 201]
        article_titles.append(f"Feed Pagination Article {i+1}")
        time.sleep(0.1)  # Small delay to ensure created timestamps differ
    
    # Create reader who will follow the author
    reader_data = {
        "user": {
            "username": "feedpagreader1",
            "email": "feedpagreader1@test.com",
            "password": "pass123"
        }
    }
    reader_response = requests.post(f"{BASE_URL}/api/users", json=reader_data)
    assert reader_response.status_code in [200, 201]
    reader_token = reader_response.json()["user"]["token"]
    reader_headers = {"Authorization": f"Token {reader_token}"}
    
    # Reader follows the author
    follow_response = requests.post(
        f"{BASE_URL}/api/profiles/feedpagauthor1/follow",
        headers=reader_headers
    )
    assert follow_response.status_code in [200, 201]
    
    # Test limit: Get feed with limit=2
    feed_response = requests.get(
        f"{BASE_URL}/api/articles/feed?limit=2",
        headers=reader_headers
    )
    assert feed_response.status_code == 200
    feed_data = feed_response.json()
    assert len(feed_data["articles"]) == 2, \
        f"Expected 2 articles with limit=2, got {len(feed_data['articles'])}"
    
    # Test offset: Get feed with limit=2, offset=2
    feed_response2 = requests.get(
        f"{BASE_URL}/api/articles/feed?limit=2&offset=2",
        headers=reader_headers
    )
    assert feed_response2.status_code == 200
    feed_data2 = feed_response2.json()
    assert len(feed_data2["articles"]) == 2, \
        f"Expected 2 articles with limit=2, offset=2, got {len(feed_data2['articles'])}"
    
    # Verify that offset=2 gives different articles than offset=0
    # Articles should be ordered by createdAt DESC, so offset=0 gives newest
    first_page_titles = [a["title"] for a in feed_data["articles"]]
    second_page_titles = [a["title"] for a in feed_data2["articles"]]
    
    # Ensure no overlap between pages
    for title in second_page_titles:
        assert title not in first_page_titles, \
            f"Article '{title}' appears on both pages - offset not working"
