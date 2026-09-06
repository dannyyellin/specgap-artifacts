from fastapi import FastAPI, Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import SQLModel, Field, Session, create_engine, select, Relationship
from pydantic import EmailStr, BaseModel, field_validator, ConfigDict
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
import jwt
import urllib.request
import urllib.error
import json

API_V1_STR = "/api/v1"
SECRET_KEY = "super-secret-key-change-me"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 24

FIRST_SUPERUSER = "admin@example.com"
FIRST_SUPERUSER_PASSWORD = "password123"

DATABASE_URL = "sqlite:///./app.db"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{API_V1_STR}/login/access-token")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class UserBase(SQLModel):
    email: EmailStr = Field(index=True, unique=True, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = True
    is_superuser: bool = False


class User(UserBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    hashed_password: str
    items: List["Item"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str):
        if v is None:
            raise ValueError("Password is required")
        if len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]):
        if v is not None and len(v) > 255:
            raise ValueError("Full name must be at most 255 characters")
        return v


class UserRegister(UserCreate):
    pass


class UserCreatePrivate(UserCreate):
    is_active: bool = True
    is_superuser: bool = False


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool

    model_config = ConfigDict(from_attributes=True)


class UsersRead(BaseModel):
    data: List[UserRead]
    count: int


class UserUpdateMe(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]):
        if v is not None and len(v) > 255:
            raise ValueError("Full name must be at most 255 characters")
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]):
        if v is not None and len(v) > 255:
            raise ValueError("Full name must be at most 255 characters")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]):
        if v is not None and (len(v) < 8 or len(v) > 128):
            raise ValueError("Password must be between 8 and 128 characters")
        return v


class UpdatePassword(BaseModel):
    current_password: str
    new_password: str

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, v: str):
        if len(v) < 8 or len(v) > 128:
            raise ValueError("Current password must be between 8 and 128 characters")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str):
        if len(v) < 8 or len(v) > 128:
            raise ValueError("New password must be between 8 and 128 characters")
        return v


class NewPassword(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str):
        if len(v) < 8 or len(v) > 128:
            raise ValueError("New password must be between 8 and 128 characters")
        return v


class Message(BaseModel):
    message: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int
    type: Optional[str] = "access"


class ItemBase(SQLModel):
    title: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, max_length=255)


class Item(ItemBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(foreign_key="user.id")
    owner: Optional[User] = Relationship(back_populates="items")


class ItemCreate(BaseModel):
    title: str
    description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str):
        if v is None:
            raise ValueError("Title is required")
        if len(v) < 1 or len(v) > 255:
            raise ValueError("Title must be between 1 and 255 characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]):
        if v is not None and len(v) > 255:
            raise ValueError("Description must be at most 255 characters")
        return v


class ItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]):
        if v is not None and (len(v) < 1 or len(v) > 255):
            raise ValueError("Title must be between 1 and 255 characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]):
        if v is not None and len(v) > 255:
            raise ValueError("Description must be at most 255 characters")
        return v


class ItemRead(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    owner_id: UUID

    model_config = ConfigDict(from_attributes=True)


class ItemsRead(BaseModel):
    data: List[ItemRead]
    count: int


def get_session():
    with Session(engine) as session:
        yield session


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None, token_type: str = "access") -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {"sub": subject, "exp": int(expire.timestamp()), "type": token_type}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid token")


def authenticate(session: Session, email: str, password: str) -> Optional[User]:
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type", "access")
        if email is None or token_type != "access":
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise credentials_exception
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_active_superuser(current_user: User = Depends(get_current_active_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user


def send_recovery_email(email_to: str, token: str):
    html = f"""
    <html>
      <body>
        <p>Password recovery</p>
        <p>Your reset token is: <strong>{token}</strong></p>
      </body>
    </html>
    """
    payload = {
        "sender": {"email": "noreply@example.com"},
        "to": [{"email": email_to}],
        "subject": "Password recovery",
        "html": html,
        "text": f"Password recovery token: {token}",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:1080/messages",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def init_superuser():
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == FIRST_SUPERUSER)).first()
        if not user:
            superuser = User(
                email=FIRST_SUPERUSER,
                full_name="Admin",
                hashed_password=get_password_hash(FIRST_SUPERUSER_PASSWORD),
                is_active=True,
                is_superuser=True,
            )
            session.add(superuser)
            session.commit()


app = FastAPI(title="User & Item Management API")
api_router = APIRouter(prefix=API_V1_STR)


@api_router.post("/login/access-token", response_model=Token)
def login_access_token(session: Session = Depends(get_session), form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(user.email)
    return Token(access_token=access_token, token_type="bearer")


@api_router.post("/users/signup", response_model=UserRead)
def signup(user_in: UserRegister, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@api_router.post("/users/", response_model=UserRead)
def create_user(user_in: UserCreatePrivate, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_superuser)):
    existing = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        is_active=user_in.is_active,
        is_superuser=user_in.is_superuser,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@api_router.get("/users/", response_model=UsersRead)
def read_users(session: Session = Depends(get_session), current_user: User = Depends(get_current_active_superuser)):
    users = session.exec(select(User)).all()
    return UsersRead(data=users, count=len(users))


@api_router.get("/users/me", response_model=UserRead)
def read_user_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@api_router.patch("/users/me", response_model=UserRead)
def update_user_me(user_in: UserUpdateMe, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)):
    if user_in.email and user_in.email != current_user.email:
        existing = session.exec(select(User).where(User.email == user_in.email)).first()
        if existing:
            raise HTTPException(status_code=409, detail="User with this email already exists")
        current_user.email = user_in.email
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@api_router.patch("/users/me/password", response_model=Message)
def update_password_me(password_in: UpdatePassword, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)):
    if not verify_password(password_in.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if password_in.current_password == password_in.new_password:
        raise HTTPException(status_code=400, detail="New password cannot be the same as the current one")
    current_user.hashed_password = get_password_hash(password_in.new_password)
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@api_router.delete("/users/me", response_model=Message)
def delete_user_me(session: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)):
    if current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Super users are not allowed to delete themselves")
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@api_router.get("/users/{user_id}", response_model=UserRead)
def read_user_by_id(user_id: UUID, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="The user with this id does not exist in the system")
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return user


@api_router.patch("/users/{user_id}", response_model=UserRead)
def update_user_by_id(user_id: UUID, user_in: UserUpdate, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_superuser)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="The user with this id does not exist in the system")
    if user_in.email and user_in.email != user.email:
        existing = session.exec(select(User).where(User.email == user_in.email)).first()
        if existing:
            raise HTTPException(status_code=409, detail="User with this email already exists")
        user.email = user_in.email
    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.password is not None:
        user.hashed_password = get_password_hash(user_in.password)
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.is_superuser is not None:
        user.is_superuser = user_in.is_superuser
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@api_router.delete("/users/{user_id}", response_model=Message)
def delete_user_by_id(user_id: UUID, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.is_superuser:
        if current_user.id == user_id:
            raise HTTPException(status_code=403, detail="Super users are not allowed to delete themselves")
    else:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")


@api_router.post("/password-recovery/{email}", response_model=Message)
def recover_password(email: EmailStr, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="The user with this email does not exist in the system")
    token = create_access_token(user.email, expires_delta=timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS), token_type="reset")
    send_recovery_email(user.email, token)
    return Message(message="Password recovery email sent")


@api_router.get("/password-recovery-html/{email}", response_model=Message)
def recover_password_html(email: EmailStr, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_superuser)):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="The user with this email does not exist in the system")
    token = create_access_token(user.email, expires_delta=timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS), token_type="reset")
    html = f"<html><body><p>Password recovery</p><p>Your reset token is: <strong>{token}</strong></p></body></html>"
    return Message(message=html)


@api_router.post("/reset-password/", response_model=Message)
def reset_password(body: NewPassword, session: Session = Depends(get_session)):
    try:
        payload = jwt.decode(body.token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")
        if not email or token_type != "reset":
            raise HTTPException(status_code=400, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    user.hashed_password = get_password_hash(body.new_password)
    session.add(user)
    session.commit()
    return Message(message="Password updated successfully")


@api_router.post("/login/test-token", response_model=UserRead)
def test_token(current_user: User = Depends(get_current_active_user)):
    return current_user


@api_router.post("/items/", response_model=ItemRead)
def create_item(item_in: ItemCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)):
    item = Item(title=item_in.title, description=item_in.description, owner_id=current_user.id)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@api_router.get("/items/", response_model=ItemsRead)
def read_items(session: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)):
    items = session.exec(select(Item)).all()
    return ItemsRead(data=items, count=len(items))


@api_router.get("/items/{item_id}", response_model=ItemRead)
def read_item(item_id: UUID, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@api_router.patch("/items/{item_id}", response_model=ItemRead)
def update_item(item_id: UUID, item_in: ItemUpdate, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="Not enough permissions")
    if item_in.title is not None:
        item.title = item_in.title
    if item_in.description is not None:
        item.description = item_in.description
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@api_router.delete("/items/{item_id}", response_model=Message)
def delete_item(item_id: UUID, session: Session = Depends(get_session), current_user: User = Depends(get_current_active_user)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="Not enough permissions")
    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")


app.include_router(api_router)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    init_superuser()