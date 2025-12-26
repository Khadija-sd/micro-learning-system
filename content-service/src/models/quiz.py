from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class QuizQuestion(BaseModel):
    text: str = Field(..., min_length=10)
    options: List[str] = Field(..., min_items=2, max_items=5)
    correct_answer: str = Field(...)
    points: int = Field(1, ge=1, le=10)
    explanation: Optional[str] = None

class QuizCreate(BaseModel):
    course_id: str = Field(...)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    questions: List[QuizQuestion] = Field(..., min_items=1)
    passing_score: int = Field(70, ge=0, le=100)

class QuizResponse(BaseModel):
    id: str
    course_id: str
    title: str
    description: Optional[str] = None
    questions: List[QuizQuestion]
    passing_score: int
    created_at: datetime
    updated_at: datetime
    attempts_count: int = 0
    average_score: float = 0.0
    
    class Config:
        from_attributes = True

class QuizSubmission(BaseModel):
    quiz_id: str
    user_id: str
    answers: List[str]  # List of selected answers
    
    class Config:
        from_attributes = True

class QuizResult(BaseModel):
    quiz_id: str
    user_id: str
    score: int
    passed: bool
    total_questions: int
    correct_answers: int
    submitted_at: datetime
    
    class Config:
        from_attributes = True