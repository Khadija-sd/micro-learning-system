from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class LessonBase(BaseModel):
    course_id: str = Field(...)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(...)
    duration_minutes: int = Field(5, ge=1, le=60)
    order: int = Field(1, ge=1)
    tags: List[str] = Field(default_factory=list)

class LessonCreate(LessonBase):
    pass

class LessonResponse(LessonBase):
    id: str
    created_at: datetime
    updated_at: datetime
    views: int = 0
    
    class Config:
        from_attributes = True