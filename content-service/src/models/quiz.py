# models/quiz.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

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

class QuizSubmissionDetail(BaseModel):
    quiz_id: str
    user_id: str
    answers: List[str]
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

class QuizResult(BaseModel):
    quiz_id: str
    user_id: str
    score: int
    percentage: float
    passed: bool
    total_questions: int
    correct_answers: int
    total_points: int
    earned_points: int
    submitted_at: datetime
    time_taken_seconds: Optional[float] = None

class UserQuizStats(BaseModel):
    user_id: str
    quiz_id: str
    best_score: int
    best_percentage: float
    attempts_count: int
    last_attempt: Optional[datetime]
    average_score: float

class QuizAttempt(BaseModel):
    id: str
    quiz_id: str
    user_id: str
    score: int
    percentage: float
    passed: bool
    submitted_at: datetime
    answers: List[str]
    correct_answers: List[bool]