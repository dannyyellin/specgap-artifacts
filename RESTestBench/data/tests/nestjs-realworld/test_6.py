"""
Scenario 6: Verify article feed only returns articles from followed users.
Create user1 (username: 'feeduser1', email: 'feeduser1@test.com', password: 'pass123'), user2 
(username: 'feedauthor1', email: 'feedauthor1@test.com', password: 'pass123'), and user3 
(username: 'feedauthor2', email: 'feedauthor2@test.com', password: 'pass123'). User2 creates 
article 'Article By Followed'. User3 creates article 'Article By Not Followed'. Using user1's 
token, GET /api/articles/feed. Verify articlesCount is 0 (no follows yet). User1 follows user2. 
GET /api/articles/feed again. Verify articlesCount is 1. Verify the articles array contains 
'Article By Followed' and does NOT contain 'Article By Not Followed'.
"""
import requests

BASE_URL = "http://localhost:3000"


def test_article_feed_only_returns_followed_users_articles():
    # Create user1 (will check feed)
    user1_data = {
        "user": {
            "username": "feeduser1",
            "email": "feeduser1@test.com",
            "password": "pass123"
        }
    }
    response1 = requests.post(f"{BASE_URL}/api/users", json=user1_data)
    assert response1.status_code == 201, f"Expected 201, got {response1.status_code}: {response1.text}"
    user1_token = response1.json()["user"]["token"]
    user1_headers = {"Authorization": f"Token {user1_token}"}
    
    # Create user2 (will be followed by user1)
    user2_data = {
        "user": {
            "username": "feedauthor1",
            "email": "feedauthor1@test.com",
            "password": "pass123"
        }
    }
    response2 = requests.post(f"{BASE_URL}/api/users", json=user2_data)
    assert response2.status_code == 201, f"Expected 201, got {response2.status_code}: {response2.text}"
    user2_token = response2.json()["user"]["token"]
    user2_headers = {"Authorization": f"Token {user2_token}"}
    
    # Create user3 (will NOT be followed by user1)
    user3_data = {
        "user": {
            "username": "feedauthor2",
            "email": "feedauthor2@test.com",
            "password": "pass123"
        }
    }
    response3 = requests.post(f"{BASE_URL}/api/users", json=user3_data)
    assert response3.status_code == 201, f"Expected 201, got {response3.status_code}: {response3.text}"
    user3_token = response3.json()["user"]["token"]
    user3_headers = {"Authorization": f"Token {user3_token}"}
    
    # User2 creates an article
    article2_data = {
        "article": {
            "title": "Article By Followed",
            "description": "Article by followed user",
            "body": "Content from followed author",
            "tagList": ["followed"]
        }
    }
    create_response2 = requests.post(
        f"{BASE_URL}/api/articles",
        json=article2_data,
        headers=user2_headers
    )
    assert create_response2.status_code == 201
    
    # User3 creates an article
    article3_data = {
        "article": {
            "title": "Article By Not Followed",
            "description": "Article by unfollowed user",
            "body": "Content from unfollowed author",
            "tagList": ["unfollowed"]
        }
    }
    create_response3 = requests.post(
        f"{BASE_URL}/api/articles",
        json=article3_data,
        headers=user3_headers
    )
    assert create_response3.status_code == 201
    
    # User1 checks feed before following anyone
    feed_response_empty = requests.get(
        f"{BASE_URL}/api/articles/feed",
        headers=user1_headers
    )
    assert feed_response_empty.status_code == 200, f"Expected 200, got {feed_response_empty.status_code}"
    feed_empty = feed_response_empty.json()
    assert feed_empty["articlesCount"] == 0, f"Expected articlesCount 0 before following, got {feed_empty['articlesCount']}"
    
    # User1 follows user2
    follow_response = requests.post(
        f"{BASE_URL}/api/profiles/feedauthor1/follow",
        headers=user1_headers
    )
    assert follow_response.status_code in [200, 201]
    
    # User1 checks feed after following user2
    feed_response = requests.get(
        f"{BASE_URL}/api/articles/feed",
        headers=user1_headers
    )
    assert feed_response.status_code == 200, f"Expected 200, got {feed_response.status_code}"
    feed = feed_response.json()
    
    assert feed["articlesCount"] == 1, f"Expected articlesCount 1 after following, got {feed['articlesCount']}"
    
    # Verify the feed contains only the followed user's article
    article_titles = [article["title"] for article in feed["articles"]]
    assert "Article By Followed" in article_titles, "Feed should contain 'Article By Followed'"
    assert "Article By Not Followed" not in article_titles, "Feed should NOT contain 'Article By Not Followed'"
