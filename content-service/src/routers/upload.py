from fastapi import APIRouter, UploadFile, File, HTTPException, status
from typing import List

from services.content_service import ContentService
from services.transformation_service import TransformationService
from utils.file_processor import FileProcessor
from models.lesson import LessonCreate, LessonResponse
from models.schemas import UserResponse
from utils.dependencies import get_current_user

router = APIRouter(
    prefix="/upload",
    tags=["upload"],
    responses={400: {"description": "Bad request"}}
)

content_service = ContentService()
transformation_service = TransformationService()

@router.post(
    "/course",
    response_model=List[LessonResponse],
    summary="Upload and transform course",
    description="Upload a course file (PDF/TXT) and transform it into micro-lessons"
)
async def upload_and_transform_course(
    file: UploadFile = File(...),
    course_id: str = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Upload course content and transform into micro-lessons"""
    # Check if user is teacher or admin
    if current_user.role not in ["teacher", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can upload course content"
        )
    
    try:
        # Process uploaded file
        content = await FileProcessor.process_upload(file)
        
        if not content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty"
            )
        
        # Split into micro-lessons
        micro_lessons = transformation_service.split_into_micro_lessons(content)
        
        # Extract keywords
        keywords = transformation_service.extract_keywords(content)
        
        # Create lessons
        lessons = []
        for i, micro_lesson in enumerate(micro_lessons):
            lesson_data = LessonCreate(
                course_id=course_id or "",
                title=micro_lesson["title"],
                content=micro_lesson["content"],
                duration_minutes=micro_lesson["estimated_minutes"],
                order=micro_lesson["order"],
                tags=keywords[:5]  # Use top 5 keywords as tags
            )
            
            lesson_id = content_service.create_lesson(lesson_data)
            lesson = content_service.get_lesson(lesson_id)
            lessons.append(lesson)
        
        return lessons
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}"
        )