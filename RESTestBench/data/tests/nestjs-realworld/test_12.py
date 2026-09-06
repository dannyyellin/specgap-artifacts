"""
Golden Test for Requirement 12: Article Filtering by Tag
Tests that articles can be filtered by tag using the ?tag= query parameter.
"""
import requests
import random
import string

BASE_URL = "http://localhost:3000"

def random_suffix():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

def test_article_filtering_by_tag():
    suffix = random_suffix()
    
    # Create user
    user_data = {
        "user": {
            "username": f"tagtest{suffix}",
            "email": f"tagtest{suffix}@test.com",
            "password": "pass123"
        }
    }
    create_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert create_response.status_code in [200, 201], f"Failed to create user: {create_response.text}"
    
    token = create_response.json()["user"]["token"]
    headers = {"Authorization": f"Token {token}"}
    
    # Create article1 with tags javascript, testing
    article1_data = {
        "article": {
            "title": f"First Tagged Article {suffix}",
            "description": "Article with javascript tag",
            "body": "Content",
            "tagList": ["javascript", "testing"]
        }
    }
    art1_response = requests.post(f"{BASE_URL}/api/articles", json=article1_data, headers=headers)
    assert art1_response.status_code in [200, 201], f"Failed to create article1: {art1_response.text}"
    
    # Create article2 with tags python, testing
    article2_data = {
        "article": {
            "title": f"Second Tagged Article {suffix}",
            "description": "Article with python tag",
            "body": "Content",
            "tagList": ["python", "testing"]
        }
    }
    art2_response = requests.post(f"{BASE_URL}/api/articles", json=article2_data, headers=headers)
    assert art2_response.status_code in [200, 201], f"Failed to create article2: {art2_response.text}"
    
    # Create article3 with tag ruby only
    article3_data = {
        "article": {
            "title": f"No Match Article {suffix}",
            "description": "Article with ruby tag",
            "body": "Content",
            "tagList": ["ruby"]
        }
    }
    art3_response = requests.post(f"{BASE_URL}/api/articles", json=article3_data, headers=headers)
    assert art3_response.status_code in [200, 201], f"Failed to create article3: {art3_response.text}"
    
    # Filter by tag=javascript - should return only article1
    filter_js_response = requests.get(f"{BASE_URL}/api/articles?tag=javascript")
    assert filter_js_response.status_code == 200, f"Expected 200, got {filter_js_response.status_code}"
    
    js_result = filter_js_response.json()
    js_titles = [a["title"] for a in js_result["articles"]]
    assert any(f"First Tagged Article {suffix}" in t for t in js_titles), f"Should contain 'First Tagged Article {suffix}', got {js_titles}"
    assert not any(f"Second Tagged Article {suffix}" in t for t in js_titles), f"Should NOT contain 'Second Tagged Article {suffix}'"
    assert not any(f"No Match Article {suffix}" in t for t in js_titles), f"Should NOT contain 'No Match Article {suffix}'"
    
    # Filter by tag=testing - should return article1 and article2
    filter_testing_response = requests.get(f"{BASE_URL}/api/articles?tag=testing")
    assert filter_testing_response.status_code == 200
    
    testing_result = filter_testing_response.json()
    testing_titles = [a["title"] for a in testing_result["articles"]]
    assert any(f"First Tagged Article {suffix}" in t for t in testing_titles), "Should contain 'First Tagged Article'"
    assert any(f"Second Tagged Article {suffix}" in t for t in testing_titles), "Should contain 'Second Tagged Article'"
    assert not any(f"No Match Article {suffix}" in t for t in testing_titles), "Should NOT contain 'No Match Article'"
