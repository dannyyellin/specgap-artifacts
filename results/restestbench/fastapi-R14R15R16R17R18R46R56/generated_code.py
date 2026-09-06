from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import EmailStr, field_validator, ConfigDict
from sqlmodel import SQLModel, Field, Session, create_engine, select, Relationship
from passlib.context import CryptContext

API_V1_STR = "/api/v1"
SECRET_KEY = "super-secret-key-change-me"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

FIRST_SUPERUSER = "admin@example.com"
FIRST_SUPERUSER_PASSWORD = "password123"

DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{API_V1_STR}/login/access-token")

app = FastAPI(title="User & Item Management Application")
api_router = APIRouter(prefix=API_V1_STR)


class UserBase(SQLModel):
    email: EmailStr = Field(index=True, unique=True, nullable=False, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = True
    is_superuser: bool = False


class User(UserBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    hashed_password: str
    items: List["Item"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=255)


class Item(ItemBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    owner_id: UUID = Field(foreign_key="user.id", nullable=False)
    owner: Optional[User] = Relationship(back_populates="items")


class UserCreate(SQLModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str):
        if v is None or len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        return v


class UserRegister(UserCreate):
    pass


class UserCreatePrivate(UserCreate):
    is_active: bool = True
    is_superuser: bool = False


class UserUpdateMe(SQLModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=255)


class UserUpdate(SQLModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None


class UpdatePassword(SQLModel):
    current_password: str
    new_password: str

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, v: str):
        if v is None or len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str):
        if v is None or len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        return v


class UserPublic(SQLModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool

    model_config = ConfigDict(from_attributes=True)


class UsersPublic(SQLModel):
    data: List[UserPublic]
    count: int


class ItemCreate(SQLModel):
    title: str
    description: Optional[str] = Field(default=None, max_length=255)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str):
        if v is None or len(v) < 1 or len(v) > 255:
            raise ValueError("Title must be between 1 and 255 characters")
        return v


class ItemUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=255)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]):
        if v is not None and (len(v) < 1 or len(v) > 255):
            raise ValueError("Title must be between 1 and 255 characters")
        return v


class ItemPublic(SQLModel):
    id: UUID
    title: str
    description: Optional[str] = None
    owner_id: UUID

    model_config = ConfigDict(from_attributes=True)


class ItemsPublic(SQLModel):
    data: List[ItemPublic]
    count: int


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class Message(SQLModel):
    message: str


def get_session():
    with Session(engine) as session:
        yield session


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(session: Session, email: str) -> Optional[User]:
    return session.exec(select(User).where(User.email == email)).first()


def authenticate(session: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(session, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = get_user_by_email(session, sub)
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


@api_router.post("/login/access-token", response_model=Token)
def login_access_token(
    session: Session = Depends(get_session),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    user = authenticate(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(user.email)
    return Token(access_token=access_token, token_type="bearer")


@api_router.post("/users/signup", response_model=UserPublic)
def signup(user_in: UserRegister, session: Session = Depends(get_session)):
    existing_user = get_user_by_email(session, user_in.email)
    if existing_user:
        if user_in.email == FIRST_SUPERUSER:
            raise HTTPException(status_code=400, detail="The user with this email already exists in the system")
        raise HTTPException(status_code=400, detail="The user with this email already exists in the system")
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


@api_router.post("/users/", response_model=UserPublic)
def create_user(
    user_in: UserCreatePrivate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_superuser),
):
    existing_user = get_user_by_email(session, user_in.email)
    if existing_user:
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


@api_router.get("/users/", response_model=UsersPublic)
def read_users(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_superuser),
):
    users = session.exec(select(User)).all()
    return UsersPublic(data=users, count=len(users))


@api_router.get("/users/me", response_model=UserPublic)
def read_user_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@api_router.patch("/users/me", response_model=UserPublic)
def update_user_me(
    user_in: UserUpdateMe,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    if user_in.email and user_in.email != current_user.email:
        existing_user = get_user_by_email(session, user_in.email)
        if existing_user:
            raise HTTPException(status_code=409, detail="User with this email already exists")
        current_user.email = user_in.email
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@api_router.patch("/users/me/password", response_model=Message)
def update_password_me(
    body: UpdatePassword,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="New password cannot be the same as the current one")
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    current_user.hashed_password = get_password_hash(body.new_password)
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@api_router.delete("/users/me", response_model=Message)
def delete_user_me(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Super users are not allowed to delete themselves")
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@api_router.get("/users/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return user


@api_router.patch("/users/{user_id}", response_model=UserPublic)
def update_user_by_id(
    user_id: UUID,
    user_in: UserUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_superuser),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="The user with this id does not exist in the system")
    if user_in.email and user_in.email != user.email:
        existing_user = get_user_by_email(session, user_in.email)
        if existing_user:
            raise HTTPException(status_code=409, detail="User with this email already exists")
        user.email = user_in.email
    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.is_superuser is not None:
        user.is_superuser = user_in.is_superuser
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@api_router.delete("/users/{user_id}", response_model=Message)
def delete_user_by_id(
    user_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_superuser),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.id == user.id and current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Super users are not allowed to delete themselves")
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")


@api_router.post("/items/", response_model=ItemPublic)
def create_item(
    item_in: ItemCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    item = Item(title=item_in.title, description=item_in.description, owner_id=current_user.id)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@api_router.get("/items/", response_model=ItemsPublic)
def read_items(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.is_superuser:
        items = session.exec(select(Item)).all()
    else:
        items = session.exec(select(Item).where(Item.owner_id == current_user.id)).all()
    return ItemsPublic(data=items, count=len(items))


@api_router.get("/items/{item_id}", response_model=ItemPublic)
def read_item(
    item_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return item


@api_router.patch("/items/{item_id}", response_model=ItemPublic)
def update_item(
    item_id: UUID,
    item_in: ItemUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
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
def delete_item(
    item_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="Not enough permissions")
    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")


app.include_router(api_router)


def init_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = get_user_by_email(session, FIRST_SUPERUSER)
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


@app.on_event("startup")
def on_startup():
    init_db()


if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)