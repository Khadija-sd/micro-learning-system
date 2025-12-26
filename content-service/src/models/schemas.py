 
from pydantic import BaseModel
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"

class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: UserRole
    
    class Config:
        from_attributes = True