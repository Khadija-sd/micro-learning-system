from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from services.content_service import ContentService
from services.transformation_service import TransformationService
from models.quiz import QuizCreate, QuizResponse, QuizSubmission, QuizResult
from models.schemas import UserResponse
from utils.dependencies import get_current_user

router = APIRouter(
    prefix="/quizzes",
    tags=["quizzes"],
    responses={404: {"description": "Not found"}}
)

content_service = ContentService()
transformation_service = TransformationService()

@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new quiz",
    description="Create a new quiz. Only teachers and admins can create quizzes."
)
async def create_quiz(
    quiz_data: QuizCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new quiz"""
    # Check if user is teacher or admin
    if current_user.role not in ["teacher", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can create quizzes"
        )
    
    quiz_id = content_service.create_quiz(quiz_data)
    return {"quiz_id": quiz_id, "message": "Quiz created successfully"}

@router.post(
    "/generate-from-lesson",
    response_model=dict,
    summary="Generate quiz from lesson",
    description="Automatically generate quiz questions from lesson content"
)
async def generate_quiz_from_lesson(
    lesson_id: str,
    num_questions: int = 5,
    current_user: UserResponse = Depends(get_current_user)
):
    """Generate quiz questions automatically from lesson content"""
    lesson = content_service.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found"
        )
    
    # Generate questions
    questions = transformation_service.generate_quiz_questions(
        lesson.content, 
        num_questions
    )
    
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not generate questions from this content"
        )
    
    # Create quiz
    quiz_data = QuizCreate(
        course_id=lesson.course_id,
        title=f"Quiz for: {lesson.title}",
        description=f"Auto-generated quiz for lesson: {lesson.title}",
        questions=questions,
        passing_score=70
    )
    
    quiz_id = content_service.create_quiz(quiz_data)
    
    return {
        "quiz_id": quiz_id,
        "questions_generated": len(questions),
        "lesson_title": lesson.title,
        "message": "Quiz generated successfully"
    }

@router.post(
    "/{quiz_id}/submit",
    response_model=QuizResult,
    summary="Submit quiz answers",
    description="Submit answers for a quiz and get results"
)
async def submit_quiz(
    quiz_id: str,
    submission: QuizSubmission,
    current_user: UserResponse = Depends(get_current_user)
):
    """Submit quiz answers"""
    # Set user ID from current user
    submission.user_id = str(current_user.id)
    submission.quiz_id = quiz_id
    
    try:
        result = content_service.submit_quiz(submission)
        
        # Publish event for analytics (to be implemented with DAPR)
        # await publish_quiz_completed_event(result)
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )