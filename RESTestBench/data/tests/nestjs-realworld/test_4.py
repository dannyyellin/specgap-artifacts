"""
Scenario 4: Verify article update changes article fields and preserves slug.
Create a user (username: 'updateuser1', email: 'updateuser1@test.com', password: 'pass123'). 
Create an article with title 'Original Title', description 'Original description', body 'Original body'. 
Extract the slug. Update the article via PUT /api/articles/{slug} with new title 'Updated Title' and 
description 'Updated description'. Verify response status is 200. Verify the response article has 
'title' equal to 'Updated Title' and 'description' equal to 'Updated description'. Retrieve the 
article by the original slug. Verify the article has the updated values.
"""
import requests

BASE_URL = "http://localhost:3000"


def test_article_update():
    # Create a user
    user_data = {
        "user": {
            "username": "updateuser1",
            "email": "updateuser1@test.com",
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
            "title": "Original Title",
            "description": "Original description",
            "body": "Original body",
            "tagList": ["original"]
        }
    }
    create_response = requests.post(
        f"{BASE_URL}/api/articles",
        json=article_data,
        headers=headers
    )
    assert create_response.status_code == 201, f"Expected 201, got {create_response.status_code}: {create_response.text}"
    
    created_article = create_response.json()
    slug = created_article["slug"]
    
    # Update the article
    update_data = {
        "article": {
            "title": "Updated Title",
            "description": "Updated description"
        }
    }
    update_response = requests.put(
        f"{BASE_URL}/api/articles/{slug}",
        json=update_data,
        headers=headers
    )
    assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
    
    updated_article = update_response.json()["article"]
    assert updated_article["title"] == "Updated Title", f"Expected title 'Updated Title', got {updated_article['title']}"
    assert updated_article["description"] == "Updated description", f"Expected description 'Updated description', got {updated_article['description']}"
    
    # Verify the slug is preserved (not regenerated based on new title)
    assert updated_article["slug"] == slug, f"Expected slug '{slug}' to be preserved, got '{updated_article['slug']}'"
    
    # Retrieve the article by original slug to verify persistence
    get_response = requests.get(f"{BASE_URL}/api/articles/{slug}")
    assert get_response.status_code == 200, f"Expected 200, got {get_response.status_code}"
    
    retrieved_article = get_response.json()["article"]
    assert retrieved_article["title"] == "Updated Title", f"Expected title 'Updated Title', got {retrieved_article['title']}"
    assert retrieved_article["description"] == "Updated description", f"Expected description 'Updated description', got {retrieved_article['description']}"
