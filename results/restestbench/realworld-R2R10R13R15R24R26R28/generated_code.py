from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from sqlmodel import SQLModel, Field, Session, create_engine, select, Relationship
from sqlalchemy import Column, Text, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
import jwt
import secrets
import re
import json

app = FastAPI()

DATABASE_URL = "sqlite:///./conduit.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "super-secret-jwt-key"
ALGORITHM = "HS256"


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{base}-{secrets.token_hex(4)}"


class FollowLink(SQLModel, table=True):
    follower_id: Optional[int] = Field(default=None, foreign_key="user.id", primary_key=True)
    following_id: Optional[int] = Field(default=None, foreign_key="user.id", primary_key=True)


class ArticleTagLink(SQLModel, table=True):
    article_id: Optional[int] = Field(default=None, foreign_key="article.id", primary_key=True)
    tag_id: Optional[int] = Field(default=None, foreign_key="tag.id", primary_key=True)


class User(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("username"), UniqueConstraint("email"))
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    email: str = Field(index=True)
    password_hash: str
    bio: Optional[str] = None
    image: Optional[str] = None

    articles: List["Article"] = Relationship(back_populates="author")
    comments: List["Comment"] = Relationship(back_populates="author")


class Tag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

    articles: List["Article"] = Relationship(back_populates="tags", link_model=ArticleTagLink)


class Article(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    title: str
    description: str = Field(sa_column=Column(Text))
    body: str = Field(sa_column=Column(Text))
    created_at: str
    updated_at: str
    author_id: int = Field(foreign_key="user.id")

    author: Optional[User] = Relationship(back_populates="articles")
    comments: List["Comment"] = Relationship(back_populates="article")
    tags: List[Tag] = Relationship(back_populates="articles", link_model=ArticleTagLink)


class Comment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    body: str = Field(sa_column=Column(Text))
    created_at: str
    updated_at: str
    author_id: int = Field(foreign_key="user.id")
    article_id: int = Field(foreign_key="article.id")

    author: Optional[User] = Relationship(back_populates="comments")
    article: Optional[Article] = Relationship(back_populates="comments")


def create_db_and_seed():
    SQLModel.metadata.create_all(engine)


@app.on_event("startup")
def on_startup():
    create_db_and_seed()


def get_session():
    with Session(engine) as session:
        yield session


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(user: User) -> str:
    payload = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def parse_token_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if authorization.startswith("Token "):
        return authorization.split(" ", 1)[1]
    if authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1]
    return None


def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
    session: Session = Depends(get_session),
) -> Optional[User]:
    token = parse_token_header(authorization)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        if not user_id:
            return None
        return session.get(User, user_id)
    except Exception:
        return None


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    user = get_current_user_optional(authorization, session)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


def profile_dict(target: User, viewer: Optional[User], session: Session):
    following = False
    if viewer and viewer.id != target.id:
        link = session.get(FollowLink, (viewer.id, target.id))
        following = link is not None
    return {
        "username": target.username,
        "bio": target.bio,
        "image": target.image,
        "following": following,
    }


def article_dict(article: Article, viewer: Optional[User], session: Session, include_comments: bool = False):
    author = session.get(User, article.author_id)
    following = False
    if viewer and author and viewer.id != author.id:
        following = session.get(FollowLink, (viewer.id, author.id)) is not None
    tags = [t.name for t in article.tags]
    comments_payload = None
    if include_comments:
        comments_payload = [comment_dict(c, viewer, session) for c in sorted(article.comments, key=lambda x: x.id or 0)]
    data = {
        "slug": article.slug,
        "title": article.title,
        "description": article.description,
        "body": article.body,
        "tagList": tags,
        "createdAt": article.created_at,
        "updatedAt": article.updated_at,
        "created": article.created_at,
        "updated": article.updated_at,
        "favorited": False,
        "favoritesCount": 0,
        "author": {
            "username": author.username if author else None,
            "bio": author.bio if author else None,
            "image": author.image if author else None,
            "following": following,
        },
    }
    if include_comments:
        data["comments"] = comments_payload
    return data


def comment_dict(comment: Comment, viewer: Optional[User], session: Session):
    author = session.get(User, comment.author_id)
    following = False
    if viewer and author and viewer.id != author.id:
        following = session.get(FollowLink, (viewer.id, author.id)) is not None
    return {
        "id": comment.id,
        "createdAt": comment.created_at,
        "updatedAt": comment.updated_at,
        "body": comment.body,
        "author": {
            "username": author.username if author else None,
            "bio": author.bio if author else None,
            "image": author.image if author else None,
            "following": following,
        },
    }


def user_dict(user: User):
    return {
        "email": user.email,
        "token": create_token(user),
        "username": user.username,
        "bio": user.bio,
        "image": user.image,
        "id": user.id,
    }


@app.post("/api/users", status_code=201)
def register(payload: dict, session: Session = Depends(get_session)):
    data = payload.get("user", {})
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    if not username or not email or not password:
        raise HTTPException(status_code=400, detail="Invalid payload")
    existing = session.exec(select(User).where((User.username == username) | (User.email == email))).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username and email must be unique")
    user = User(username=username, email=email, password_hash=hash_password(password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Username and email must be unique")
    session.refresh(user)
    return {"user": user_dict(user)}


@app.post("/api/users/login", status_code=201)
def login(payload: dict, session: Session = Depends(get_session)):
    data = payload.get("user", {})
    email = data.get("email")
    password = data.get("password")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(password or "", user.password_hash):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"user": user_dict(user)}


@app.get("/api/user")
def get_user(current_user: User = Depends(get_current_user)):
    return {"user": user_dict(current_user)}


@app.put("/api/user")
def update_user(payload: dict, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    data = payload.get("user", {})
    if "email" in data and data["email"] != current_user.email:
        existing = session.exec(select(User).where(User.email == data["email"])).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username and email must be unique")
        current_user.email = data["email"]
    if "username" in data and data["username"] != current_user.username:
        existing = session.exec(select(User).where(User.username == data["username"])).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username and email must be unique")
        current_user.username = data["username"]
    if "password" in data and data["password"]:
        current_user.password_hash = hash_password(data["password"])
    if "bio" in data:
        current_user.bio = data["bio"]
    if "image" in data:
        current_user.image = data["image"]
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return {"user": user_dict(current_user)}


@app.get("/api/profiles/{username}")
def get_profile(username: str, viewer: Optional[User] = Depends(get_current_user_optional), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"profile": profile_dict(user, viewer, session)}


@app.post("/api/profiles/{username}/follow")
def follow_user(username: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    target = session.exec(select(User).where(User.username == username)).first()
    if not target:
        raise HTTPException(status_code=404, detail="Profile not found")
    if current_user.id != target.id and not session.get(FollowLink, (current_user.id, target.id)):
        session.add(FollowLink(follower_id=current_user.id, following_id=target.id))
        session.commit()
    return {"profile": profile_dict(target, current_user, session)}


@app.delete("/api/profiles/{username}/follow")
def unfollow_user(username: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    target = session.exec(select(User).where(User.username == username)).first()
    if not target:
        raise HTTPException(status_code=404, detail="Profile not found")
    link = session.get(FollowLink, (current_user.id, target.id))
    if link:
        session.delete(link)
        session.commit()
    return {"profile": profile_dict(target, current_user, session)}


def attach_tags(session: Session, article: Article, tag_list: List[str]):
    article.tags.clear()
    session.add(article)
    session.flush()
    for tag_name in tag_list:
        tag = session.exec(select(Tag).where(Tag.name == tag_name)).first()
        if not tag:
            tag = Tag(name=tag_name)
            session.add(tag)
            session.flush()
        if tag not in article.tags:
            article.tags.append(tag)


@app.post("/api/articles", status_code=201)
def create_article(payload: dict, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    data = payload.get("article", {})
    title = data.get("title", "")
    description = data.get("description", "")
    body = data.get("body", "")
    tag_list = data.get("tagList", []) or []
    ts = now_iso()
    article = Article(
        slug=slugify(title),
        title=title,
        description=description,
        body=body,
        created_at=ts,
        updated_at=ts,
        author_id=current_user.id,
    )
    session.add(article)
    session.flush()
    attach_tags(session, article, tag_list)
    session.commit()
    session.refresh(article)
    return {"article": article_dict(article, current_user, session)}


@app.get("/api/articles/{slug}")
def get_article(slug: str, viewer: Optional[User] = Depends(get_current_user_optional), session: Session = Depends(get_session)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        return {}
    return {"article": article_dict(article, viewer, session)}


@app.put("/api/articles/{slug}")
def update_article(slug: str, payload: dict, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        return {}
    if article.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    data = payload.get("article", {})
    if "title" in data:
        article.title = data["title"]
    if "description" in data:
        article.description = data["description"]
    if "body" in data:
        article.body = data["body"]
    if "tagList" in data:
        attach_tags(session, article, data.get("tagList", []) or [])
    article.updated_at = now_iso()
    session.add(article)
    session.commit()
    session.refresh(article)
    return {"article": article_dict(article, current_user, session)}


@app.delete("/api/articles/{slug}")
def delete_article(slug: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        return {}
    if article.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    for comment in list(article.comments):
        session.delete(comment)
    article.tags.clear()
    session.delete(article)
    session.commit()
    return {"status": "ok"}


@app.get("/api/articles")
def list_articles(
    tag: Optional[str] = Query(default=None),
    author: Optional[str] = Query(default=None),
    limit: int = Query(default=20),
    offset: int = Query(default=0),
    viewer: Optional[User] = Depends(get_current_user_optional),
    session: Session = Depends(get_session),
):
    articles = session.exec(select(Article)).all()
    if author:
        author_user = session.exec(select(User).where(User.username == author)).first()
        if author_user:
            articles = [a for a in articles if a.author_id == author_user.id]
        else:
            articles = []
    if tag is not None:
        articles = [a for a in articles if tag in [t.name for t in a.tags]]
    articles = sorted(articles, key=lambda a: a.id or 0, reverse=True)
    total = len(articles)
    articles = articles[offset:offset + limit]
    return {"articles": [article_dict(a, viewer, session) for a in articles], "articlesCount": total}


@app.get("/api/articles/feed")
def feed_articles(
    limit: int = Query(default=20),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    links = session.exec(select(FollowLink).where(FollowLink.follower_id == current_user.id)).all()
    followed_ids = [l.following_id for l in links]
    if not followed_ids:
        return {"articles": [], "articlesCount": 0}
    articles = session.exec(select(Article)).all()
    articles = [a for a in articles if a.author_id in followed_ids]
    articles = sorted(articles, key=lambda a: a.id or 0, reverse=True)
    total = len(articles)
    articles = articles[offset:offset + limit]
    return {"articles": [article_dict(a, current_user, session) for a in articles], "articlesCount": total}


@app.post("/api/articles/{slug}/comments")
def add_comment(slug: str, payload: dict, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        return {}
    body = payload.get("comment", {}).get("body", "")
    ts = now_iso()
    comment = Comment(body=body, created_at=ts, updated_at=ts, author_id=current_user.id, article_id=article.id)
    session.add(comment)
    session.commit()
    session.refresh(article)
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    return {"article": article_dict(article, current_user, session, include_comments=True)}


@app.get("/api/articles/{slug}/comments")
def get_comments(slug: str, viewer: Optional[User] = Depends(get_current_user_optional), session: Session = Depends(get_session)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        return {"comments": []}
    comments = sorted(article.comments, key=lambda c: c.id or 0)
    return {"comments": [comment_dict(c, viewer, session) for c in comments]}


@app.delete("/api/articles/{slug}/comments/{comment_id}")
def delete_comment(slug: str, comment_id: int, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        return {}
    comment = session.get(Comment, comment_id)
    if not comment or comment.article_id != article.id:
        return {"status": "ok"}
    if comment.author_id != current_user.id and article.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    session.delete(comment)
    session.commit()
    return {"status": "ok"}


@app.get("/api/tags")
def get_tags(session: Session = Depends(get_session)):
    tags = session.exec(select(Tag)).all()
    return {"tags": [t.name for t in tags]}


@app.delete("/api/users/{email}")
def delete_user_by_email(email: str, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        return {"status": "ok"}
    try:
        session.delete(user)
        session.commit()
        return {"status": "ok"}
    except Exception as e:
        session.rollback()
        return JSONResponse(status_code=500, content={"detail": str(e)})


@app.get("/")
def root():
    return {"status": "ok"}