"""
Authentication endpoints for the High School Management System API
"""

from secrets import token_urlsafe
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException

from ..database import teachers_collection, verify_password

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

active_sessions: Dict[str, str] = {}


def require_authenticated_session(username: str, session_token: str) -> Dict[str, Any]:
    """Validate that a teacher has an active authenticated session."""
    if active_sessions.get(session_token) != username:
        raise HTTPException(status_code=401, detail="Invalid session")

    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        active_sessions.pop(session_token, None)
        raise HTTPException(status_code=401, detail="Invalid session")

    return teacher


@router.post("/login")
def login(username: str, password: str) -> Dict[str, Any]:
    """Login a teacher account"""
    # Find the teacher in the database
    teacher = teachers_collection.find_one({"_id": username})

    # Verify password using Argon2 verifier from database.py
    if not teacher or not verify_password(teacher.get("password", ""), password):
        raise HTTPException(
            status_code=401, detail="Invalid username or password")

    for token, token_username in list(active_sessions.items()):
        if token_username == username:
            del active_sessions[token]

    session_token = token_urlsafe(32)
    active_sessions[session_token] = username

    # Return teacher information (excluding password)
    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"],
        "session_token": session_token
    }


@router.get("/check-session")
def check_session(
    username: str,
    session_token: str = Header(..., alias="X-Session-Token")
) -> Dict[str, Any]:
    """Check if a session is valid by username"""
    teacher = require_authenticated_session(username, session_token)

    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"],
        "session_token": session_token
    }
