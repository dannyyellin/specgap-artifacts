"""
Scenario 3: Verify article creation generates slug correctly from title and article can be retrieved by slug.
Create a user (username: 'author1', email: 'author1@test.com', password: 'pass123') and authenticate. 
Create an article with title 'My Test Article', description 'Test description', body 'Article body content', 
tagList ['testing', 'nestjs']. Verify response status is 201. Verify the returned article has 'title' equal 
to 'My Test Article', 'description' equal to 'Test description', 'tagList' containing 'testing' and 'nestjs', 
and 'slug' starting with 'my-test-article-' (lowercase with hyphen suffix). Extract the slug. Retrieve the 
article via GET /api/articles/{slug}. Verify status 200 and the returned article title is 'My Test Article'.
"""
import requests

BASE_URL = "http://localhost:3000"


def test_article_creation_with_slug_generation():
    # Create a user
    user_data = {
        "user": {
            "username": "author1",
            "email": "author1@test.com",
            "password": "pass123"
        }
    }
    response = requests.post(f"{BASE_URL}/api/users", json=user_data)
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    token = response.json()["user"]["token"]
    headers = {"Authorization": f"Token {token}"}
    
    # Create an article
    article_data = {
        "article": {
            "title": "My Test Article",
            "description": "Test description",
            "body": "Article body content",
            "tagList": ["testing", "nestjs"]
        }
    }
    create_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article_data,
        headers=headers
    )
    assert create_response.status_code == 201, f"Expected 201, got {create_response.status_code}: {create_response.text}"
    
    created_article = create_response.json()
    
    # Verify article fields
    assert created_article["title"] == "My Test Article", f"Expected title 'My Test Article', got {created_article.get('title')}"
    assert created_article["description"] == "Test description", f"Expected description 'Test description', got {created_article.get('description')}"
    assert "testing" in created_article["tagList"], "tagList should contain 'testing'"
    assert "nestjs" in created_article["tagList"], "tagList should contain 'nestjs'"
    
    # Verify slug format (lowercase with suffix)
    slug = created_article["slug"]
    assert slug.startswith("my-test-article-"), f"Slug should start with 'my-test-article-', got {slug}"
    
    # Retrieve article by slug
    get_response = requests.get(f"{BASE_URL}/api/articles/{slug}")
    assert get_response.status_code == 200, f"Expected 200, got {get_response.status_code}: {get_response.text}"
    
    retrieved_article = get_response.json()["article"]
    assert retrieved_article["title"] == "My Test Article", f"Expected title 'My Test Article', got {retrieved_article['title']}"
