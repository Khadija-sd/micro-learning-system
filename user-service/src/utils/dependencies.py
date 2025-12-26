 
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.schemas import UserResponse
from ..services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UserResponse:
    """Dependency to get current user from JWT token"""
    return AuthService.get_current_user(token, db)

async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """Dependency to check if user is active"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_admin_user(
    current_user: UserResponse = Depends(get_current_active_user)
) -> UserResponse:
    """Dependency to check if user is admin"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user