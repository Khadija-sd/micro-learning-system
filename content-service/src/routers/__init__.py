 
from .courses import router as courses_router
from .lessons import router as lessons_router
from .quizzes import router as quizzes_router
from .upload import router as upload_router

__all__ = ["courses_router", "lessons_router", "quizzes_router", "upload_router"]