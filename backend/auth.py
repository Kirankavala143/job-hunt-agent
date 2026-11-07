
import os
import re
import sqlite3
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
from jose import jwt, JWTError
from email_validator import validate_email, EmailNotValidError
from pydantic import BaseModel, EmailStr, Field


# ---------------- CONFIGURATION ----------------

DATABASE_PATH = str(Path(__file__).resolve().with_name("jobhunt_users.db"))

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)
    print(
        "WARNING: JWT_SECRET_KEY is not set. "
        "Set a permanent secret before production."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# ---------------- DATABASE ----------------

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_auth_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                role_title TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT ''
            )
        """)
        user_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "role_title" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN role_title TEXT NOT NULL DEFAULT ''"
            )
        if "location" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN location TEXT NOT NULL DEFAULT ''"
            )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL CHECK (status IN ('Enabled', 'Paused')),
                last_run TEXT NOT NULL DEFAULT '',
                next_run TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        connection.commit()


initialize_auth_database()


# ---------------- REQUEST MODELS ----------------

class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


# ---------------- PASSWORD HELPERS ----------------

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            stored_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


# ---------------- JWT HELPERS ----------------

def create_access_token(user_id: int, email: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expires
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_user_from_token(token: str):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = int(payload.get("sub"))
        email = payload.get("email")

        if not email:
            return None

        with get_connection() as connection:
            user = connection.execute(
                """
                SELECT id, full_name, email, role_title, location
                FROM users
                WHERE id = ?
                """,
                (user_id,)
            ).fetchone()

        return dict(user) if user else None

    except (JWTError, ValueError, TypeError):
        return None


# ---------------- AUTH OPERATIONS ----------------

def register_user(data: RegisterRequest):
    full_name = data.full_name.strip()
    email = str(data.email).strip().lower()

    if len(full_name) < 2:
        raise ValueError("Full name must contain at least 2 characters.")

    if len(data.password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    password_hash = hash_password(data.password)

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (
                    full_name,
                    email,
                    password_hash,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    full_name,
                    email,
                    password_hash,
                    datetime.now(timezone.utc).isoformat()
                )
            )
            connection.commit()
            user_id = cursor.lastrowid

    except sqlite3.IntegrityError:
        raise ValueError("An account with this email already exists.")

    return {
        "id": user_id,
        "full_name": full_name,
        "email": email,
        "role_title": "",
        "location": "",
    }


def authenticate_user(data: LoginRequest):
    email = str(data.email).strip().lower()

    with get_connection() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

    if not user or not verify_password(
        data.password,
        user["password_hash"]
    ):
        return None

    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "role_title": user["role_title"],
        "location": user["location"],
    }
