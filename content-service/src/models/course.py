from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

class CourseStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class CourseBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    teacher_id: str = Field(...)
    subject: str = Field(...)
    tags: List[str] = Field(default_factory=list)
    status: CourseStatus = CourseStatus.DRAFT

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[CourseStatus] = None
    tags: Optional[List[str]] = None

class CourseResponse(CourseBase):
    id: str
    created_at: datetime
    updated_at: datetime
    lesson_count: int = 0
    quiz_count: int = 0
    
    class Config:
        from_attributes = True