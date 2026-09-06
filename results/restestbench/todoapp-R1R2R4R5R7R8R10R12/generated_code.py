from datetime import datetime, timedelta
from typing import Optional, List

import jwt
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import EmailStr
from passlib.context import CryptContext
from sqlmodel import SQLModel, Field, Session, create_engine, select

app = FastAPI(title="Todo List Application")

DATABASE_URL = "sqlite:///./todos.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SECRET_KEY = "super-secret-jwt-key-change-me"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: EmailStr = Field(index=True, unique=True)
    password_hash: str


class Todo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    isComplete: bool = False
    user_id: int = Field(foreign_key="user.id", index=True)


class UserRegister(SQLModel):
    email: EmailStr
    password: str


class UserLogin(SQLModel):
    email: EmailStr
    password: str


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(SQLModel):
    id: int
    email: EmailStr


class TodoCreate(SQLModel):
    title: str
    isComplete: bool = False


class TodoUpdate(SQLModel):
    id: Optional[int] = None
    title: str
    isComplete: bool


class TodoResponse(SQLModel):
    id: int
    title: str
    isComplete: bool


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


def get_session():
    with Session(engine) as session:
        yield session


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = session.get(User, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


@app.post("/users/register", response_model=UserResponse)
def register_user(user_in: UserRegister, session: Session = Depends(get_session)):
    existing_user = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(email=user_in.email, password_hash=hash_password(user_in.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.post("/users/login", response_model=TokenResponse)
def login_user(user_in: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == user_in.email)).first()
    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token)


@app.get("/todos", response_model=List[TodoResponse])
def list_todos(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    todos = session.exec(select(Todo).where(Todo.user_id == current_user.id)).all()
    return todos


@app.get("/todos/{id}", response_model=TodoResponse)
def get_todo(
    id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    todo = session.exec(
        select(Todo).where(Todo.id == id, Todo.user_id == current_user.id)
    ).first()
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    return todo


@app.post("/todos", response_model=TodoResponse)
def create_todo(
    todo_in: TodoCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    todo = Todo(
        title=todo_in.title,
        isComplete=todo_in.isComplete,
        user_id=current_user.id,
    )
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo


@app.put("/todos/{id}", response_model=TodoResponse)
def update_todo(
    id: int,
    todo_in: TodoUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    todo = session.exec(
        select(Todo).where(Todo.id == id, Todo.user_id == current_user.id)
    ).first()
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    todo.title = todo_in.title
    todo.isComplete = todo_in.isComplete
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo


@app.delete("/todos/{id}")
def delete_todo(
    id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    todo = session.exec(
        select(Todo).where(Todo.id == id, Todo.user_id == current_user.id)
    ).first()
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    session.delete(todo)
    session.commit()
    return {"message": "Todo deleted"}