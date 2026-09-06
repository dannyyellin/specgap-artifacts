"""
Golden test for Requirement 28: Any authenticated user can update/delete any article (no authorization check - security vulnerability)
"""

import requests
import pytest

BASE_URL = "http://localhost:3000"


def test_unauthorized_article_update_and_delete():
    """
    Test that any authenticated user can update AND delete any article, regardless of ownership.
    This demonstrates a security vulnerability in the implementation.
    """
    
    # Create user1 (article owner)
    user1_data = {
        "user": {
            "username": "owner1",
            "email": "owner1@test.com",
            "password": "pass123"
        }
    }
    user1_response = requests.post(f"{BASE_URL}/api/users", json=user1_data)
    assert user1_response.status_code in [200, 201], f"Failed to create user1: {user1_response.text}"
    token1 = user1_response.json()["user"]["token"]
    headers1 = {"Authorization": f"Token {token1}"}
    
    # Create user2 (attacker - not the owner)
    user2_data = {
        "user": {
            "username": "attacker1",
            "email": "attacker1@test.com",
            "password": "pass123"
        }
    }
    user2_response = requests.post(f"{BASE_URL}/api/users", json=user2_data)
    assert user2_response.status_code in [200, 201], f"Failed to create user2: {user2_response.text}"
    token2 = user2_response.json()["user"]["token"]
    headers2 = {"Authorization": f"Token {token2}"}
    
    # ========== PART 1: Test unauthorized UPDATE ==========
    
    # User1 creates an article
    article_data = {
        "article": {
            "title": "Original Owner Article",
            "description": "Original description",
            "body": "Original body content",
            "tagList": []
        }
    }
    article_response = requests.post(f"{BASE_URL}/api/articles", json=article_data, headers=headers1)
    assert article_response.status_code in [200, 201], f"Failed to create article: {article_response.text}"
    slug1 = article_response.json()["slug"]
    
    # Verify original article
    get_response = requests.get(f"{BASE_URL}/api/articles/{slug1}")
    assert get_response.status_code == 200
    article = get_response.json()["article"]
    assert article["title"] == "Original Owner Article", f"Original title mismatch: {article['title']}"
    
    # User2 (NOT the owner) updates the article
    update_data = {
        "article": {
            "title": "Hacked By User2",
            "description": "Attacker modified this"
        }
    }
    update_response = requests.put(f"{BASE_URL}/api/articles/{slug1}", json=update_data, headers=headers2)
    assert update_response.status_code in [200, 201], f"Update should succeed (vulnerability): {update_response.text}"
    
    # Verify the PUT response shows updated values (catches wrong return value mutation)
    updated_article = update_response.json()["article"]
    assert updated_article["title"] == "Hacked By User2", f"PUT response title should be updated, got: {updated_article['title']}"
    
    # Verify the article was modified by the attacker (catches no-save mutation)
    get_response = requests.get(f"{BASE_URL}/api/articles/{slug1}")
    assert get_response.status_code == 200
    article = get_response.json()["article"]
    assert article["title"] == "Hacked By User2", f"GET title should be changed by attacker, got: {article['title']}"
    
    # ========== PART 2: Test unauthorized DELETE ==========
    
    # User1 creates another article for delete test
    article_data2 = {
        "article": {
            "title": "Article To Delete",
            "description": "This will be deleted by attacker",
            "body": "Article body content",
            "tagList": []
        }
    }
    article_response2 = requests.post(f"{BASE_URL}/api/articles", json=article_data2, headers=headers1)
    assert article_response2.status_code in [200, 201], f"Failed to create second article: {article_response2.text}"
    slug2 = article_response2.json()["slug"]
    
    # Verify article exists
    get_response = requests.get(f"{BASE_URL}/api/articles/{slug2}")
    assert get_response.status_code == 200
    article = get_response.json()["article"]
    assert article is not None, "Article should exist before deletion"
    
    # User2 (NOT the owner) deletes the article
    delete_response = requests.delete(f"{BASE_URL}/api/articles/{slug2}", headers=headers2)
    assert delete_response.status_code in [200, 201, 204], f"Delete should succeed (vulnerability): {delete_response.text}"
    
    # Verify the article is gone (catches delete wrong slug mutation)
    get_response = requests.get(f"{BASE_URL}/api/articles/{slug2}")
    article_data = get_response.json()
    assert article_data.get("article") is None, f"Article should be deleted, got: {article_data}"
