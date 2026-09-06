"""
Golden Test for Requirement 13: Article Filtering by Author
Tests that articles can be filtered by author using the ?author= query parameter.
"""
import requests
import random
import string

BASE_URL = "http://localhost:3000"

def random_suffix():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

def test_article_filtering_by_author():
    suffix = random_suffix()
    
    # Create user1 (author1)
    user1_data = {
        "user": {
            "username": f"author1{suffix}",
            "email": f"author1{suffix}@test.com",
            "password": "pass123"
        }
    }
    user1_response = requests.post(f"{BASE_URL}/api/users", json=user1_data)
    assert user1_response.status_code in [200, 201], f"Failed to create user1: {user1_response.text}"
    user1_token = user1_response.json()["user"]["token"]
    user1_headers = {"Authorization": f"Token {user1_token}"}
    
    # Create user2 (author2)
    user2_data = {
        "user": {
            "username": f"author2{suffix}",
            "email": f"author2{suffix}@test.com",
            "password": "pass123"
        }
    }
    user2_response = requests.post(f"{BASE_URL}/api/users", json=user2_data)
    assert user2_response.status_code in [200, 201], f"Failed to create user2: {user2_response.text}"
    user2_token = user2_response.json()["user"]["token"]
    user2_headers = {"Authorization": f"Token {user2_token}"}
    
    # User1 creates article
    article1_data = {
        "article": {
            "title": f"Article By Author1 {suffix}",
            "description": "Written by author1",
            "body": "Content",
            "tagList": []
        }
    }
    art1_response = requests.post(f"{BASE_URL}/api/articles", json=article1_data, headers=user1_headers)
    assert art1_response.status_code in [200, 201], f"Failed to create article1: {art1_response.text}"
    
    # User2 creates article
    article2_data = {
        "article": {
            "title": f"Article By Author2 {suffix}",
            "description": "Written by author2",
            "body": "Content",
            "tagList": []
        }
    }
    art2_response = requests.post(f"{BASE_URL}/api/articles", json=article2_data, headers=user2_headers)
    assert art2_response.status_code in [200, 201], f"Failed to create article2: {art2_response.text}"
    
    # Filter by author=author1{suffix}
    filter_author1_response = requests.get(f"{BASE_URL}/api/articles?author=author1{suffix}")
    assert filter_author1_response.status_code == 200, f"Expected 200, got {filter_author1_response.status_code}"
    
    author1_result = filter_author1_response.json()
    author1_titles = [a["title"] for a in author1_result["articles"]]
    assert any(f"Article By Author1 {suffix}" in t for t in author1_titles), f"Should contain 'Article By Author1 {suffix}', got {author1_titles}"
    assert not any(f"Article By Author2 {suffix}" in t for t in author1_titles), f"Should NOT contain 'Article By Author2 {suffix}'"
    
    # Filter by author=author2{suffix}
    filter_author2_response = requests.get(f"{BASE_URL}/api/articles?author=author2{suffix}")
    assert filter_author2_response.status_code == 200
    
    author2_result = filter_author2_response.json()
    author2_titles = [a["title"] for a in author2_result["articles"]]
    assert any(f"Article By Author2 {suffix}" in t for t in author2_titles), "Should contain 'Article By Author2'"
    assert not any(f"Article By Author1 {suffix}" in t for t in author2_titles), "Should NOT contain 'Article By Author1'"
    
    # Verify author1 result count is exactly 1 for our suffix
    matching_author1 = [a for a in author1_result["articles"] if f"Author1 {suffix}" in a["title"]]
    assert len(matching_author1) == 1, f"Expected exactly 1 article from author1{suffix}, got {len(matching_author1)}"
