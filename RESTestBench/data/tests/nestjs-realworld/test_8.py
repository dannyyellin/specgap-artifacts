"""
Scenario 8: Verify comment deletion removes comment from article comments list.
Create a user (username: 'delcommentuser1', email: 'delcommentuser1@test.com', password: 'pass123'). 
Create an article with title 'Delete Comment Test'. Extract the slug. Create a comment with body 
'Comment to delete'. Extract the comment id from the response. Verify the article has 1 comment. 
Delete the comment via DELETE /api/articles/{slug}/comments/{id}. Verify response status is 200. 
GET the article's comments. Verify the comments array is empty or does not contain the deleted 
comment body.
"""
import requests

BASE_URL = "http://localhost:3000"


def test_comment_deletion():
    # Create a user
    user_data = {
        "user": {
            "username": "delcommentuser1",
            "email": "delcommentuser1@test.com",
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
            "title": "Delete Comment Test",
            "description": "Article for comment deletion testing",
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
    
    # Create a comment on the article
    comment_data = {
        "comment": {
            "body": "Comment to delete"
        }
    }
    comment_response = requests.post(
        f"{BASE_URL}/api/articles/{slug}/comments",
        json=comment_data,
        headers=headers
    )
    assert comment_response.status_code in [200, 201], f"Expected 200/201, got {comment_response.status_code}: {comment_response.text}"
    
    # Extract comment id and verify body was saved correctly
    comment_result = comment_response.json()
    comments = comment_result["article"]["comments"]
    assert len(comments) == 1, f"Expected 1 comment, got {len(comments)}"
    comment_id = comments[0]["id"]
    # Verify the comment body was stored correctly (catches body mutation)
    assert comments[0]["body"] == "Comment to delete", f"Expected comment body 'Comment to delete', got '{comments[0]['body']}'"
    
    # Delete the comment
    delete_response = requests.delete(
        f"{BASE_URL}/api/articles/{slug}/comments/{comment_id}",
        headers=headers
    )
    assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
    
    # GET comments and verify deletion
    get_comments_response = requests.get(
        f"{BASE_URL}/api/articles/{slug}/comments",
        headers=headers
    )
    assert get_comments_response.status_code == 200
    
    comments_result = get_comments_response.json()
    remaining_comments = comments_result["comments"]
    
    # Verify comment with "Comment to delete" body no longer exists
    for comment in remaining_comments:
        assert comment["body"] != "Comment to delete", "Deleted comment should not be in comments list"
