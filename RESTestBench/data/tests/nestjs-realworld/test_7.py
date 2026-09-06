"""
Scenario 7: Verify comment creation adds comment to article and can be retrieved.
Create a user (username: 'commentuser1', email: 'commentuser1@test.com', password: 'pass123'). 
Create an article with title 'Comment Test Article'. Extract the slug. Create a comment on the 
article via POST /api/articles/{slug}/comments with body 'This is my test comment'. Verify 
response status is 200. Verify the response article has comments array with length >= 1. GET 
the comments for the article via GET /api/articles/{slug}/comments. Verify status 200. Verify 
the comments array contains a comment with body 'This is my test comment'. Verify the comment 
has an 'id' field that is a number.
"""
import requests

BASE_URL = "http://localhost:3000"


def test_comment_creation_and_retrieval():
    # Create a user
    user_data = {
        "user": {
            "username": "commentuser1",
            "email": "commentuser1@test.com",
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
            "title": "Comment Test Article",
            "description": "Article for comment testing",
            "body": "Article body content",
            "tagList": ["comments"]
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
    
    # Create a comment on the article
    comment_data = {
        "comment": {
            "body": "This is my test comment"
        }
    }
    comment_response = requests.post(
        f"{BASE_URL}/api/articles/{slug}/comments",
        json=comment_data,
        headers=headers
    )
    assert comment_response.status_code in [200, 201], f"Expected 200/201, got {comment_response.status_code}: {comment_response.text}"
    
    comment_result = comment_response.json()
    assert "article" in comment_result, "Response should contain 'article' object"
    assert len(comment_result["article"]["comments"]) >= 1, "Article should have at least 1 comment"
    
    # GET comments for the article
    get_comments_response = requests.get(
        f"{BASE_URL}/api/articles/{slug}/comments",
        headers=headers
    )
    assert get_comments_response.status_code == 200, f"Expected 200, got {get_comments_response.status_code}"
    
    comments_result = get_comments_response.json()
    assert "comments" in comments_result, "Response should contain 'comments' array"
    
    # Find the comment with our body
    found_comment = None
    for comment in comments_result["comments"]:
        if comment["body"] == "This is my test comment":
            found_comment = comment
            break
    
    assert found_comment is not None, "Comment with body 'This is my test comment' should exist"
    assert "id" in found_comment, "Comment should have 'id' field"
    assert isinstance(found_comment["id"], int), f"Comment id should be a number, got {type(found_comment['id'])}"
