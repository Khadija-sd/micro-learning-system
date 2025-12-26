from fastapi import APIRouter, HTTPException, Form
from typing import Dict, Any, List
import logging

from src.services.transformation_service import transformation_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/transform",
    tags=["transformation"],
    responses={400: {"description": "Bad request"}}
)

@router.post("/")
async def transform_content(
    content: str = Form(..., description="Contenu textuel à transformer"),
    target_duration: int = Form(5, description="Durée cible des micro-leçons en minutes", ge=1, le=30)
) -> Dict[str, Any]:
    """
    Transformer un contenu textuel en micro-leçons
    
    - **content**: Texte du cours complet
    - **target_duration**: Durée souhaitée pour chaque micro-leçon (5 min par défaut)
    
    Retourne les micro-leçons générées avec résumés et mots-clés
    """
    logger.info(f"Transformation demandée: durée={target_duration}min, contenu={len(content)} caractères")
    
    if not content or len(content.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Le contenu doit faire au moins 50 caractères"
        )
    
    try:
        # 1. Découper en micro-leçons
        micro_lessons = transformation_service.split_into_micro_lessons(
            content, 
            target_duration
        )
        
        # 2. Extraire les mots-clés globaux
        keywords = transformation_service.extract_keywords(content)
        
        # 3. Générer un résumé global
        summary = transformation_service.generate_summary(content)
        
        logger.info(f"✅ Transformation réussie: {len(micro_lessons)} leçons créées")
        
        return {
            "success": True,
            "total_lessons": len(micro_lessons),
            "total_duration": sum(lesson["estimated_minutes"] for lesson in micro_lessons),
            "keywords": keywords[:10],
            "summary": summary,
            "micro_lessons": micro_lessons
        }
        
    except Exception as e:
        logger.error(f"Erreur de transformation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Échec de la transformation: {str(e)}"
        )

@router.post("/generate-quiz")
async def generate_quiz_from_content(
    content: str = Form(...),
    num_questions: int = Form(5, ge=1, le=20)
) -> Dict[str, Any]:
    """
    Générer un quiz automatiquement à partir d'un contenu
    
    - **content**: Texte du cours
    - **num_questions**: Nombre de questions à générer
    """
    logger.info(f"Génération de quiz: {num_questions} questions")
    
    try:
        questions = transformation_service.generate_quiz_questions(
            content, 
            num_questions
        )
        
        return {
            "success": True,
            "questions_generated": len(questions),
            "questions": questions
        }
        
    except Exception as e:
        logger.error(f"Erreur génération quiz: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Échec génération quiz: {str(e)}"
        )