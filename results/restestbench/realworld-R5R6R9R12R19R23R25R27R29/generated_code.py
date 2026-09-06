from fastapi import FastAPI, Depends, HTTPException, Header, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Field, Session, create_engine, select, Relationship
from sqlalchemy import Column, Text, UniqueConstraint
from typing import Optional, List
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
import secrets
import re
import json

SECRET_KEY = "super-secret-jwt-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sqlite_url = "sqlite:///./conduit.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})


def now_utc():
    return datetime.utcnow()


def slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    suffix = secrets.token_hex(4)
    return f"{base}-{suffix}"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail={"errors": {"body": ["Invalid token"]}})


class FollowLink(SQLModel, table=True):
    follower_id: Optional[int] = Field(default=None, foreign_key="user.id", primary_key=True)
    following_id: Optional[int] = Field(default=None, foreign_key="user.id", primary_key=True)


class ArticleTagLink(SQLModel, table=True):
    article_id: Optional[int] = Field(default=None, foreign_key="article.id", primary_key=True)
    tag_id: Optional[int] = Field(default=None, foreign_key="tag.id", primary_key=True)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
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
    __table_args__ = (UniqueConstraint("slug"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True)
    title: str
    description: str = Field(default="", sa_column=Column(Text))
    body: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc)
    author_id: int = Field(foreign_key="user.id")

    author: Optional[User] = Relationship(back_populates="articles")
    comments: List["Comment"] = Relationship(back_populates="article")
    tags: List[Tag] = Relationship(back_populates="articles", link_model=ArticleTagLink)


class Comment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    body: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    author_id: int = Field(foreign_key="user.id")
    article_id: int = Field(foreign_key="article.id")

    author: Optional[User] = Relationship(back_populates="comments")
    article: Optional[Article] = Relationship(back_populates="comments")


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


def get_session():
    with Session(engine) as session:
        yield session


def parse_token_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Token":
        return None
    return parts[1]


def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
    session: Session = Depends(get_session),
) -> Optional[User]:
    token = parse_token_header(authorization)
    if not token:
        return None
    user_id = decode_token(token)
    user = session.get(User, user_id)
    if not user:
        return None
    return user


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    token = parse_token_header(authorization)
    if not token:
        raise HTTPException(status_code=401, detail={"errors": {"body": ["Authorization required"]}})
    user_id = decode_token(token)
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail={"errors": {"body": ["User not found"]}})
    return user


def user_response(user: User):
    return {
        "user": {
            "email": user.email,
            "token": create_token(user.id),
            "username": user.username,
            "bio": user.bio,
            "image": user.image,
        }
    }


def is_following(session: Session, viewer: Optional[User], target: User) -> bool:
    if not viewer:
        return False
    link = session.get(FollowLink, (viewer.id, target.id))
    return link is not None


def profile_response(session: Session, target: User, viewer: Optional[User]):
    return {
        "profile": {
            "username": target.username,
            "bio": target.bio,
            "image": target.image,
            "following": is_following(session, viewer, target),
        }
    }


def article_response(session: Session, article: Article, viewer: Optional[User] = None, include_comments: bool = False):
    session.refresh(article)
    author = session.get(User, article.author_id)
    tags = [tag.name for tag in article.tags]
    comments_payload = []
    if include_comments:
        comments = session.exec(select(Comment).where(Comment.article_id == article.id).order_by(Comment.id)).all()
        for c in comments:
            c_author = session.get(User, c.author_id)
            comments_payload.append({
                "id": c.id,
                "createdAt": c.created_at.isoformat() + "Z",
                "updatedAt": c.updated_at.isoformat() + "Z",
                "body": c.body,
                "author": {
                    "username": c_author.username if c_author else None,
                    "bio": c_author.bio if c_author else None,
                    "image": c_author.image if c_author else None,
                    "following": is_following(session, viewer, c_author) if c_author else False,
                },
            })
    return {
        "article": {
            "slug": article.slug,
            "title": article.title,
            "description": article.description,
            "body": article.body,
            "tagList": tags,
            "createdAt": article.created_at.isoformat() + "Z",
            "updatedAt": article.updated_at.isoformat() + "Z",
            "favorited": False,
            "favoritesCount": 0,
            "author": {
                "username": author.username if author else None,
                "bio": author.bio if author else None,
                "image": author.image if author else None,
                "following": is_following(session, viewer, author) if author else False,
            },
            **({"comments": comments_payload} if include_comments else {}),
        }
    }


def comment_response(session: Session, comment: Comment, viewer: Optional[User] = None):
    author = session.get(User, comment.author_id)
    return {
        "id": comment.id,
        "createdAt": comment.created_at.isoformat() + "Z",
        "updatedAt": comment.updated_at.isoformat() + "Z",
        "body": comment.body,
        "author": {
            "username": author.username if author else None,
            "bio": author.bio if author else None,
            "image": author.image if author else None,
            "following": is_following(session, viewer, author) if author else False,
        },
    }


def get_or_create_tags(session: Session, tag_names: List[str]) -> List[Tag]:
    tags = []
    for name in tag_names:
        existing = session.exec(select(Tag).where(Tag.name == name)).first()
        if existing:
            tags.append(existing)
        else:
            tag = Tag(name=name)
            session.add(tag)
            session.commit()
            session.refresh(tag)
            tags.append(tag)
    return tags


@app.post("/api/users", status_code=201)
def register(payload: dict, session: Session = Depends(get_session)):
    user_data = payload.get("user", {})
    username = user_data.get("username")
    email = user_data.get("email")
    password = user_data.get("password")
    if not username or not email or not password:
        raise HTTPException(status_code=422, detail={"errors": {"body": ["Missing fields"]}})
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=422, detail={"errors": {"email": ["has already been taken"]}})
    if session.exec(select(User).where(User.username == username)).first():
        raise HTTPException(status_code=422, detail={"errors": {"username": ["has already been taken"]}})
    user = User(username=username, email=email, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user_response(user)


@app.post("/api/users/login", status_code=201)
def login(payload: dict, session: Session = Depends(get_session)):
    user_data = payload.get("user", {})
    email = user_data.get("email")
    password = user_data.get("password")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail={"errors": {"body": ["email or password is invalid"]}})
    return user_response(user)


@app.get("/api/user")
def get_user(current_user: User = Depends(get_current_user)):
    return user_response(current_user)


@app.put("/api/user")
def update_user(payload: dict, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    user_data = payload.get("user", {})
    if "email" in user_data and user_data["email"]:
        current_user.email = user_data["email"]
    if "username" in user_data and user_data["username"]:
        current_user.username = user_data["username"]
    if "password" in user_data and user_data["password"]:
        current_user.password_hash = hash_password(user_data["password"])
    if "bio" in user_data:
        current_user.bio = user_data["bio"]
    if "image" in user_data:
        current_user.image = user_data["image"]
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return user_response(current_user)


@app.get("/api/profiles/{username}")
def get_profile(username: str, session: Session = Depends(get_session), viewer: Optional[User] = Depends(get_current_user_optional)):
    target = session.exec(select(User).where(User.username == username)).first()
    if not target:
        raise HTTPException(status_code=404, detail={"errors": {"body": ["Profile not found"]}})
    return profile_response(session, target, viewer)


@app.post("/api/profiles/{username}/follow", status_code=201)
def follow_profile(username: str, session: Session = Depends(get_session), viewer: User = Depends(get_current_user)):
    target = session.exec(select(User).where(User.username == username)).first()
    if not target:
        raise HTTPException(status_code=404, detail={"errors": {"body": ["Profile not found"]}})
    if viewer.id == target.id:
        raise HTTPException(status_code=400, detail={"errors": {"body": ["followerId and followingId cannot be equal"]}})
    existing = session.get(FollowLink, (viewer.id, target.id))
    if not existing:
        session.add(FollowLink(follower_id=viewer.id, following_id=target.id))
        session.commit()
    return profile_response(session, target, viewer)


@app.delete("/api/profiles/{username}/follow")
def unfollow_profile(username: str, session: Session = Depends(get_session), viewer: User = Depends(get_current_user)):
    target = session.exec(select(User).where(User.username == username)).first()
    if not target:
        raise HTTPException(status_code=404, detail={"errors": {"body": ["Profile not found"]}})
    if viewer.id == target.id:
        raise HTTPException(status_code=400, detail={"errors": {"body": ["followerId and followingId cannot be equal"]}})
    existing = session.get(FollowLink, (viewer.id, target.id))
    if existing:
        session.delete(existing)
        session.commit()
    return profile_response(session, target, viewer)


@app.post("/api/articles", status_code=201)
def create_article(payload: dict, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    article_data = payload.get("article", {})
    title = article_data.get("title", "")
    description = article_data.get("description", "") or ""
    body = article_data.get("body", "") or ""
    tag_list = article_data.get("tagList", [])
    article = Article(
        slug=slugify(title),
        title=title,
        description=description,
        body=body,
        author_id=current_user.id,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    session.add(article)
    session.commit()
    session.refresh(article)
    tags = get_or_create_tags(session, tag_list)
    article.tags = tags
    session.add(article)
    session.commit()
    session.refresh(article)
    return article_response(session, article, current_user)


@app.get("/api/articles")
def list_articles(
    author: Optional[str] = Query(default=None),
    limit: int = Query(default=20),
    offset: int = Query(default=0),
    session: Session = Depends(get_session),
    viewer: Optional[User] = Depends(get_current_user_optional),
):
    query = select(Article)
    if author:
        author_user = session.exec(select(User).where(User.username == author)).first()
        if author_user:
            query = query.where(Article.author_id == author_user.id)
        else:
            return {"articles": [], "articlesCount": 0}
    all_articles = session.exec(query.order_by(Article.created_at.desc(), Article.id.desc())).all()
    total = len(all_articles)
    paged = all_articles[offset:offset + limit]
    return {
        "articles": [article_response(session, a, viewer)["article"] for a in paged],
        "articlesCount": total,
    }


@app.get("/api/articles/{slug}")
def get_article(slug: str, session: Session = Depends(get_session), viewer: Optional[User] = Depends(get_current_user_optional)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        return {}
    return article_response(session, article, viewer)


@app.put("/api/articles/{slug}")
def update_article(slug: str, payload: dict, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        return {}
    article_data = payload.get("article", {})
    if "title" in article_data and article_data["title"] is not None:
        article.title = article_data["title"]
    if "description" in article_data and article_data["description"] is not None:
        article.description = article_data["description"]
    if "body" in article_data and article_data["body"] is not None:
        article.body = article_data["body"]
    if "tagList" in article_data and article_data["tagList"] is not None:
        article.tags = get_or_create_tags(session, article_data["tagList"])
    article.updated_at = now_utc()
    session.add(article)
    session.commit()
    session.refresh(article)
    return article_response(session, article, current_user)


@app.delete("/api/articles/{slug}")
def delete_article(slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        return {}
    comments = session.exec(select(Comment).where(Comment.article_id == article.id)).all()
    for c in comments:
        session.delete(c)
    session.delete(article)
    session.commit()
    return {}


@app.post("/api/articles/{slug}/comments")
def add_comment(slug: str, payload: dict, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        raise HTTPException(status_code=404, detail={"errors": {"body": ["Article not found"]}})
    body = payload.get("comment", {}).get("body", "")
    comment = Comment(body=body, author_id=current_user.id, article_id=article.id, created_at=now_utc(), updated_at=now_utc())
    session.add(comment)
    session.commit()
    session.refresh(comment)
    return article_response(session, article, current_user, include_comments=True)


@app.get("/api/articles/{slug}/comments")
def get_comments(slug: str, session: Session = Depends(get_session), viewer: Optional[User] = Depends(get_current_user_optional)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        raise HTTPException(status_code=404, detail={"errors": {"body": ["Article not found"]}})
    comments = session.exec(select(Comment).where(Comment.article_id == article.id).order_by(Comment.id)).all()
    return {"comments": [comment_response(session, c, viewer) for c in comments]}


@app.delete("/api/articles/{slug}/comments/{comment_id}")
def delete_comment(slug: str, comment_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    article = session.exec(select(Article).where(Article.slug == slug)).first()
    if not article:
        raise HTTPException(status_code=404, detail={"errors": {"body": ["Article not found"]}})
    comment = session.get(Comment, comment_id)
    if comment and comment.article_id == article.id:
        session.delete(comment)
        session.commit()
    return {"status": "ok"}