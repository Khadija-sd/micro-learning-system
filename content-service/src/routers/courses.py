from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional
from bson import ObjectId

from src.database import get_db, object_id_to_str, str_to_object_id
from src.models.course import CourseCreate, CourseResponse

router = APIRouter(
    prefix="/course",
    tags=["courses"],
    responses={404: {"description": "Course not found"}}
)

@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_course(course: CourseCreate):
    """
    Créer un nouveau cours
    
    - **title**: Titre du cours
    - **description**: Description détaillée
    - **teacher_id**: ID de l'enseignant
    - **subject**: Matière
    - **tags**: Mots-clés
    - **status**: Statut (draft/published/archived)
    """
    db = get_db()
    
    if not db:
        raise HTTPException(
            status_code=503,
            detail="Database not available"
        )
    
    try:
        course_data = course.dict()
        course_data["created_at"] = course_data["updated_at"] = {
            "$date": {"$numberLong": str(int(datetime.utcnow().timestamp() * 1000))}
        }
        course_data["lesson_count"] = 0
        course_data["quiz_count"] = 0
        
        result = db.courses.insert_one(course_data)
        course_id = str(result.inserted_id)
        
        return {
            "id": course_id,
            "message": "Course created successfully",
            "title": course.title
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create course: {str(e)}"
        )

@router.get("/", response_model=List[CourseResponse])
async def get_courses(
    teacher_id: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Récupérer la liste des cours"""
    db = get_db()
    
    if not db:
        return []  # Mode mémoire
    
    query = {}
    if teacher_id:
        query["teacher_id"] = teacher_id
    if subject:
        query["subject"] = subject
    
    cursor = db.courses.find(query).skip(skip).limit(limit)
    courses = []
    
    for course in cursor:
        courses.append(object_id_to_str(course))
    
    return courses

@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: str):
    """Récupérer un cours spécifique par ID"""
    db = get_db()
    
    if not db:
        raise HTTPException(
            status_code=404,
            detail="Course not found (database unavailable)"
        )
    
    try:
        course = db.courses.find_one({"_id": ObjectId(course_id)})
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        return object_id_to_str(course)
        
    except:
        raise HTTPException(status_code=404, detail="Course not found")