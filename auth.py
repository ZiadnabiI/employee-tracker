"""
Authentication module for Employee Tracker
Handles JWT tokens and password hashing
"""
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status, Request, Depends
from fastapi.responses import RedirectResponse

# --- Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
TOKEN_EXPIRE_HOURS = 24

# Simple in-memory token storage (for production, use Redis or database)
active_tokens = {}

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt"""
    salt = "employee_tracker_salt"  # In production, use unique salt per user
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return hash_password(plain_password) == hashed_password

def create_token(supervisor_id: int, company_id: int, is_super_admin: bool = False) -> str:
    """Create an authentication token"""
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    
    active_tokens[token] = {
        "supervisor_id": supervisor_id,
        "company_id": company_id,
        "is_super_admin": is_super_admin,
        "expires": expires
    }
    return token

def verify_token(token: str) -> Optional[dict]:
    """Verify a token and return its data"""
    if token not in active_tokens:
        return None
    
    token_data = active_tokens[token]
    if datetime.utcnow() > token_data["expires"]:
        # Token expired, remove it
        del active_tokens[token]
        return None
    
    return token_data

def invalidate_token(token: str):
    """Remove a token (logout)"""
    if token in active_tokens:
        del active_tokens[token]

def get_token_from_cookies(request: Request) -> Optional[str]:
    """Extract token from cookies"""
    return request.cookies.get("auth_token")

def get_current_supervisor(request: Request) -> dict:
    """Get the current logged-in supervisor from request cookies"""
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return token_data

def require_auth(request: Request):
    """Dependency that requires authentication"""
    return get_current_supervisor(request)

def require_super_admin(request: Request):
    """Dependency that requires super admin"""
    supervisor = get_current_supervisor(request)
    if not supervisor.get("is_super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return supervisor
