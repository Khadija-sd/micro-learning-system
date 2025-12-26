from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional

from services.content_service import ContentService
from models.lesson import LessonResponse
from models.schemas import UserResponse
from utils.dependencies import get_current_user

router = APIRouter(
    prefix="/lessons",
    tags=["lessons"],
    responses={404: {"description": "Not found"}}
)

content_service = ContentService()

@router.get(
    "/",
    response_model=List[LessonResponse],
    summary="Get lessons",
    description="Get list of lessons, optionally filtered by course"
)
async def get_lessons(
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records")
):
    """Get lessons (optionally filtered by course)"""
    if course_id:
        lessons = content_service.get_course_lessons(course_id)
    else:
        # For now, return empty list
        lessons = []
    
    return lessons[skip:skip + limit]

@router.get(
    "/{lesson_id}",
    response_model=LessonResponse,
    summary="Get lesson by ID",
    description="Get detailed information about a specific lesson"
)
async def get_lesson(
    lesson_id: str,
    increment_view: bool = Query(True, description="Whether to increment view count")
):
    """Get lesson by ID"""
    lesson = content_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )
    
    # Increment view count
    if increment_view:
        content_service.increment_lesson_views(lesson_id)
    
    return lesson