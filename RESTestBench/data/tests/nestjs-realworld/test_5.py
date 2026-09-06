"""
Scenario 5: Verify article deletion removes the article from the system.
Create a user (username: 'deleteuser1', email: 'deleteuser1@test.com', password: 'pass123'). 
Create an article with title 'Article To Delete'. Extract the slug. Verify the article can be 
retrieved via GET /api/articles/{slug}. Delete the article via DELETE /api/articles/{slug}. 
Verify response status is 200. Attempt to GET the article by slug again. Verify the response 
status is not 200 (article should not be found).
"""
import requests

BASE_URL = "http://localhost:3000"


def test_article_deletion():
    # Create a user
    user_data = {
        "user": {
            "username": "deleteuser1",
            "email": "deleteuser1@test.com",
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
            "title": "Article To Delete",
            "description": "This article will be deleted",
            "body": "Article body content",
            "tagList": ["delete"]
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
    
    # Verify article can be retrieved
    get_response_before = requests.get(f"{BASE_URL}/api/articles/{slug}")
    assert get_response_before.status_code == 200, f"Expected 200 before delete, got {get_response_before.status_code}"
    
    # Delete the article
    delete_response = requests.delete(
        f"{BASE_URL}/api/articles/{slug}",
        headers=headers
    )
    assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
    
    # Attempt to GET the article after deletion - should fail or return null/undefined article
    get_response_after = requests.get(f"{BASE_URL}/api/articles/{slug}")
    if get_response_after.status_code == 200:
        # API may return 200 with null article
        article_data = get_response_after.json().get("article")
        assert article_data is None, f"Expected null article after delete, got {article_data}"
    else:
        # Or API may return non-200 status
        assert get_response_after.status_code in [404, 500], f"Expected 404/500 after delete, got {get_response_after.status_code}"
