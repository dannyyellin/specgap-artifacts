"""
Golden Test for Requirement 15: Article Pagination (limit/offset)
Tests that articles can be paginated using limit and offset query parameters.
"""
import requests
import random
import string
import time

BASE_URL = "http://localhost:3000"

def random_suffix():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

def test_article_pagination():
    suffix = random_suffix()
    
    # Create user
    user_data = {
        "user": {
            "username": f"paginuser{suffix}",
            "email": f"paginuser{suffix}@test.com",
            "password": "pass123"
        }
    }
    create_response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert create_response.status_code in [200, 201], f"Failed to create user: {create_response.text}"
    
    token = create_response.json()["user"]["token"]
    headers = {"Authorization": f"Token {token}"}
    
    # Create 5 articles with small delays to ensure different timestamps for ordering
    article_titles = []
    for i in range(1, 6):
        article_data = {
            "article": {
                "title": f"Pagination Article {i} {suffix}",
                "description": f"Article number {i}",
                "body": f"Content for article {i}",
                "tagList": [f"pagination{suffix}"]
            }
        }
        art_response = requests.post(f"{BASE_URL}/api/articles", json=article_data, headers=headers)
        assert art_response.status_code in [200, 201], f"Failed to create article {i}: {art_response.text}"
        article_titles.append(f"Pagination Article {i} {suffix}")
        time.sleep(0.1)  # Small delay to ensure different creation times
    
    # Filter by our unique tag to only get our articles
    # GET /api/articles?tag=pagination{suffix}&limit=2
    limit2_response = requests.get(f"{BASE_URL}/api/articles?tag=pagination{suffix}&limit=2")
    assert limit2_response.status_code == 200
    
    limit2_result = limit2_response.json()
    # articlesCount should be total (5), but articles array should have only 2
    assert len(limit2_result["articles"]) == 2, f"Expected 2 articles with limit=2, got {len(limit2_result['articles'])}"
    
    # Save the first 2 articles for comparison
    first_batch_slugs = [a["slug"] for a in limit2_result["articles"]]
    
    # GET /api/articles?tag=pagination{suffix}&limit=2&offset=2
    offset2_response = requests.get(f"{BASE_URL}/api/articles?tag=pagination{suffix}&limit=2&offset=2")
    assert offset2_response.status_code == 200
    
    offset2_result = offset2_response.json()
    assert len(offset2_result["articles"]) == 2, f"Expected 2 articles with offset=2, got {len(offset2_result['articles'])}"
    
    # These should be DIFFERENT from the first batch
    second_batch_slugs = [a["slug"] for a in offset2_result["articles"]]
    for slug in second_batch_slugs:
        assert slug not in first_batch_slugs, f"Offset should return different articles, but {slug} appears in both batches"
    
    # GET /api/articles?tag=pagination{suffix}&limit=10 - should return all 5
    all_response = requests.get(f"{BASE_URL}/api/articles?tag=pagination{suffix}&limit=10")
    assert all_response.status_code == 200
    
    all_result = all_response.json()
    assert len(all_result["articles"]) == 5, f"Expected 5 articles with limit=10, got {len(all_result['articles'])}"
    
    # Verify all our articles are in the response
    all_titles = [a["title"] for a in all_result["articles"]]
    for title in article_titles:
        assert any(title in t for t in all_titles), f"Article '{title}' should be in results"
