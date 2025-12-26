from datetime import datetime
from typing import List, Optional, Dict, Any
from bson.objectid import ObjectId

from database import Database
from models.course import CourseCreate, CourseUpdate, CourseResponse
from models.lesson import LessonCreate, LessonResponse
from models.quiz import QuizCreate, QuizResponse, QuizSubmission, QuizResult

class ContentService:
    def __init__(self):
        self.db = Database()
    
    # Course methods
    def create_course(self, course_data: CourseCreate) -> str:
        """Create a new course"""
        course_dict = course_data.dict()
        course_dict["created_at"] = datetime.utcnow()
        course_dict["updated_at"] = datetime.utcnow()
        course_dict["lesson_count"] = 0
        course_dict["quiz_count"] = 0
        
        course_id = self.db.create_course(course_dict)
        return course_id
    
    def get_course(self, course_id: str) -> Optional[CourseResponse]:
        """Get course by ID"""
        course = self.db.get_course(course_id)
        if course:
            course["id"] = str(course.pop("_id"))
            return CourseResponse(**course)
        return None
    
    def get_courses_by_teacher(self, teacher_id: str) -> List[CourseResponse]:
        """Get courses by teacher ID"""
        courses_data = self.db.get_courses_by_teacher(teacher_id)
        courses = []
        
        for course in courses_data:
            course["id"] = str(course.pop("_id"))
            courses.append(CourseResponse(**course))
        
        return courses
    
    def update_course(self, course_id: str, update_data: CourseUpdate) -> bool:
        """Update course"""
        update_dict = update_data.dict(exclude_unset=True)
        update_dict["updated_at"] = datetime.utcnow()
        
        return self.db.update_course(course_id, update_dict)
    
    # Lesson methods
    def create_lesson(self, lesson_data: LessonCreate) -> str:
        """Create a new lesson"""
        lesson_dict = lesson_data.dict()
        lesson_dict["created_at"] = datetime.utcnow()
        lesson_dict["updated_at"] = datetime.utcnow()
        lesson_dict["views"] = 0
        
        lesson_id = self.db.create_lesson(lesson_dict)
        
        # Update course lesson count
        if lesson_data.course_id:
            course = self.db.get_course(lesson_data.course_id)
            if course:
                self.db.update_course(
                    lesson_data.course_id,
                    {"lesson_count": course.get("lesson_count", 0) + 1}
                )
        
        return lesson_id
    
    def get_lesson(self, lesson_id: str) -> Optional[LessonResponse]:
        """Get lesson by ID"""
        lesson = self.db.get_lesson(lesson_id)
        if lesson:
            lesson["id"] = str(lesson.pop("_id"))
            return LessonResponse(**lesson)
        return None
    
    def get_course_lessons(self, course_id: str) -> List[LessonResponse]:
        """Get all lessons for a course"""
        lessons_data = self.db.get_course_lessons(course_id)
        lessons = []
        
        for lesson in lessons_data:
            lesson["id"] = str(lesson.pop("_id"))
            lessons.append(LessonResponse(**lesson))
        
        return lessons
    
    def increment_lesson_views(self, lesson_id: str):
        """Increment lesson view count"""
        self.db.increment_lesson_views(lesson_id)
    
    # Quiz methods
    def create_quiz(self, quiz_data: QuizCreate) -> str:
        """Create a new quiz"""
        quiz_dict = quiz_data.dict()
        quiz_dict["created_at"] = datetime.utcnow()
        quiz_dict["updated_at"] = datetime.utcnow()
        quiz_dict["attempts_count"] = 0
        quiz_dict["average_score"] = 0.0
        
        quiz_id = self.db.create_quiz(quiz_dict)
        
        # Update course quiz count
        if quiz_data.course_id:
            course = self.db.get_course(quiz_data.course_id)
            if course:
                self.db.update_course(
                    quiz_data.course_id,
                    {"quiz_count": course.get("quiz_count", 0) + 1}
                )
        
        return quiz_id
    
    def get_quiz(self, quiz_id: str) -> Optional[QuizResponse]:
        """Get quiz by ID"""
        quiz = self.db.get_quiz(quiz_id)
        if quiz:
            quiz["id"] = str(quiz.pop("_id"))
            return QuizResponse(**quiz)
        return None
    
    def submit_quiz(self, submission: QuizSubmission) -> QuizResult:
        """Submit quiz answers and get result"""
        result_dict = self.db.submit_quiz(submission)
        
        # Convert to QuizResult model
        quiz = self.db.get_quiz(submission.quiz_id)
        if quiz:
            questions = quiz.get("questions", [])
            correct_answers = 0
            
            for i, question in enumerate(questions):
                if i < len(submission.answers):
                    if submission.answers[i] == question.get("correct_answer"):
                        correct_answers += 1
            
            return QuizResult(
                quiz_id=result_dict["quiz_id"],
                user_id=result_dict["user_id"],
                score=result_dict["score"],
                passed=result_dict["passed"],
                total_questions=len(questions),
                correct_answers=correct_answers,
                submitted_at=result_dict["submitted_at"]
            )
        
        raise ValueError("Quiz not found")