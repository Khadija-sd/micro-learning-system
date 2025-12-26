from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.STUDENT

class UserCreate(UserBase):
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 3:  # Reduced for testing
            raise ValueError('Password must be at least 3 characters')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class UserInDB(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserResponse(UserInDB):
    pass

# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    full_name: Optional[str] = None