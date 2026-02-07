"""
Authentication module for Employee Tracker
Handles JWT tokens and password hashing
"""
import os
import bcrypt
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status, Request, Depends
from fastapi.responses import RedirectResponse
from database import SessionLocal, AuthToken

# --- Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required. Set it before starting the server.")
TOKEN_EXPIRE_HOURS = 24

def hash_password(password: str) -> str:
    """Hash a password using bcrypt with automatic salt generation
    
    Note: Existing SHA-256 hashed passwords in the database will no longer match.
    Users with old password hashes may need to reset their passwords.
    Consider implementing a migration strategy that checks both formats during transition.
    """
    # bcrypt requires bytes input
    password_bytes = password.encode('utf-8')
    # Generate salt and hash in one step
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    # Return as string for database storage
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash"""
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def create_token(supervisor_id: int, company_id: int, is_super_admin: bool = False) -> str:
    """Create an authentication token and store it in the database"""
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    
    # Store token in database
    session = SessionLocal()
    try:
        db_token = AuthToken(
            token=token,
            supervisor_id=supervisor_id,
            company_id=company_id,
            is_super_admin=1 if is_super_admin else 0,
            expires=expires
        )
        session.add(db_token)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    
    return token

def verify_token(token: str) -> Optional[dict]:
    """Verify a token by querying the database and return its data"""
    session = SessionLocal()
    try:
        db_token = session.query(AuthToken).filter(AuthToken.token == token).first()
        
        if not db_token:
            return None
        
        # Check if token expired
        if datetime.utcnow() > db_token.expires:
            # Token expired, remove it
            try:
                session.delete(db_token)
                session.commit()
            except Exception:
                session.rollback()
                # Still return None even if deletion failed
            return None
        
        # Return token data in the same format as before
        return {
            "supervisor_id": db_token.supervisor_id,
            "company_id": db_token.company_id,
            "is_super_admin": bool(db_token.is_super_admin),
            "expires": db_token.expires
        }
    finally:
        session.close()

def invalidate_token(token: str):
    """Remove a token from database (logout)"""
    session = SessionLocal()
    try:
        db_token = session.query(AuthToken).filter(AuthToken.token == token).first()
        if db_token:
            session.delete(db_token)
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

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
