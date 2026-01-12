import os
from datetime import datetime, timedelta
from typing import List
from urllib.parse import quote_plus

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from pydantic import BaseModel, EmailStr, Field

# ======================================================
# LOAD ENV
# ======================================================
load_dotenv()

def must_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"ENV '{key}' tidak ditemukan / kosong. Cek file .env")
    return val

SECRET_KEY = must_env("JWT_SECRET")

DB_USER = must_env("DB_USER")
DB_PASSWORD = must_env("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = must_env("DB_NAME")

# encode password MySQL (jaga-jaga kalau ada karakter spesial)
DB_PASSWORD_ENC = quote_plus(DB_PASSWORD)

# ======================================================
# APP CONFIG
# ======================================================
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

app = FastAPI(title="JWT MySQL Backend")

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
bearer_scheme = HTTPBearer()

# ======================================================
# DATABASE (MySQL)
# ======================================================
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD_ENC}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

# ======================================================
# MODELS
# ======================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    owner_email = Column(String(255), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(String(2000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# create tables
Base.metadata.create_all(bind=engine)

# ======================================================
# DB DEPENDENCY
# ======================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ======================================================
# JWT HELPERS
# ======================================================
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def create_access_token(subject_email: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {"sub": subject_email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        return email
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

def require_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    email = decode_token(creds.credentials)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

# ======================================================
# SCHEMAS
# ======================================================
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class NoteCreate(BaseModel):
    title: str
    content: str

class NoteOut(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

# ======================================================
# AUTH ENDPOINTS
# ======================================================
@app.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password)
    )
    db.add(user)
    db.commit()

    return {"message": "registered"}

@app.post("/login", response_model=TokenResponse, status_code=200)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = create_access_token(subject_email=user.email)
    return TokenResponse(access_token=token)

# ======================================================
# CRUD ENDPOINTS (PROTECTED)
# ======================================================
@app.get("/notes", response_model=List[NoteOut], status_code=200)
def list_notes(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return (
        db.query(Note)
        .filter(Note.owner_email == user.email)
        .order_by(Note.id.desc())
        .all()
    )

@app.post("/notes", response_model=NoteOut, status_code=201)
def create_note(
    payload: NoteCreate,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    note = Note(
        owner_email=user.email,
        title=payload.title,
        content=payload.content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

@app.put("/notes/{note_id}", response_model=NoteOut, status_code=200)
def update_note(
    note_id: int,
    payload: NoteCreate,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    note = (
        db.query(Note)
        .filter(Note.id == note_id, Note.owner_email == user.email)
        .first()
    )
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    note.title = payload.title
    note.content = payload.content
    db.commit()
    db.refresh(note)
    return note

@app.delete("/notes/{note_id}", status_code=200)
def delete_note(
    note_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    note = (
        db.query(Note)
        .filter(Note.id == note_id, Note.owner_email == user.email)
        .first()
    )
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    db.delete(note)
    db.commit()
    return {"message": "deleted"}