from fastapi import FastAPI, HTTPException, Form
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
import uvicorn
import logging
from datetime import datetime
import os
import time
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== CONFIGURATION MONGODB ==========
# Lecture des variables d'environnement
MONGODB_HOST = os.getenv("MONGODB_URL", "mongodb://admin:password@mongodb:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "contentdb")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")

# Variables globales - initialisées à None
db = None
client = None
memory_storage = None

# ========== FONCTION DE CONNEXION MONGODB ==========
def connect_to_mongodb():
    """Connexion à MongoDB avec retry"""
    global db, client, memory_storage
    
    # Construire l'URL complète
    MONGODB_URL = f"{MONGODB_HOST}/{MONGODB_DB}?authSource=admin"
    logger.info(f"🔌 Tentative connexion MongoDB: {MONGODB_HOST}")
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Tentative {attempt + 1}/{max_retries}...")
            
            # Importer ici pour éviter les problèmes d'import
            from pymongo import MongoClient
            
            # Connexion avec timeout réduit
            client = MongoClient(
                MONGODB_URL, 
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=5000
            )
            
            # Test connexion
            client.admin.command('ping')
            logger.info("✅ MongoDB connecté avec succès!")
            
            # Base de données
            db = client[MONGODB_DB]
            
            # Créer les collections si elles n'existent pas
            collections = ["courses", "lessons", "quizzes", "quiz_submissions"]
            
            existing_collections = db.list_collection_names()
            for collection_name in collections:
                if collection_name not in existing_collections:
                    db.create_collection(collection_name)
                    logger.info(f"📁 Collection créée: {collection_name}")
            
            logger.info(f"📊 Collections disponibles: {existing_collections}")
            memory_storage = None  # Mode MongoDB activé
            return True
            
        except Exception as e:
            logger.warning(f"⚠️  Échec connexion MongoDB (tentative {attempt + 1}): {str(e)[:100]}")
            if attempt < max_retries - 1:
                logger.info(f"⏳ Attente {retry_delay}s avant nouvelle tentative...")
                time.sleep(retry_delay)
    
    # Si toutes les tentatives échouent, utiliser le mode mémoire
    logger.error(f"❌ Impossible de se connecter à MongoDB après {max_retries} tentatives")
    logger.warning("⚠️  Activation du mode mémoire (sans persistance)")
    
    # Mode secours en mémoire
    db = None
    client = None
    memory_storage = {
        "courses": {},
        "lessons": {}, 
        "quizzes": {},
        "quiz_submissions": [],
        "_id_counter": 1
    }
    
    return False

# ========== MODÈLES ==========
class CourseStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    teacher_id: str
    subject: str
    tags: List[str] = []
    status: CourseStatus = CourseStatus.DRAFT

class LessonCreate(BaseModel):
    course_id: str
    title: str
    content: str
    duration_minutes: int = 5
    order: int = 1
    tags: List[str] = []

class QuizQuestion(BaseModel):
    text: str
    options: List[str]
    correct_answer: str
    points: int = 1

class QuizCreate(BaseModel):
    course_id: str
    title: str
    description: Optional[str] = None
    questions: List[QuizQuestion]
    passing_score: int = 70

class QuizSubmission(BaseModel):
    quiz_id: str
    user_id: str
    answers: List[str]

class TransformRequest(BaseModel):
    content: str
    target_duration: int = 5

# ========== APPLICATION ==========
app = FastAPI(
    title="Content Service - Micro Learning",
    version="2.0.0",
    description="Service de gestion de contenu pédagogique",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ========== FONCTIONS UTILITAIRES ==========
def get_memory_storage():
    """Retourne le stockage mémoire, le créé si nécessaire"""
    global memory_storage
    if memory_storage is None:
        memory_storage = {
            "courses": {},
            "lessons": {}, 
            "quizzes": {},
            "quiz_submissions": [],
            "_id_counter": 1
        }
    return memory_storage

def generate_memory_id():
    """Générer un ID pour le mode mémoire"""
    storage = get_memory_storage()
    storage["_id_counter"] += 1
    return str(storage["_id_counter"])

def is_mongodb_connected():
    """Vérifie si MongoDB est connecté"""
    global db, client
    if db is not None and client is not None:
        try:
            client.admin.command('ping')
            return True
        except:
            return False
    return False

def mongo_to_dict(doc):
    """Convertir document MongoDB en dict avec id string"""
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc

# ========== EVENT HANDLERS ==========
@app.on_event("startup")
async def startup_event():
    """Exécuté au démarrage de l'application"""
    # Créer le répertoire uploads s'il n'existe pas
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        logger.info(f"📁 Répertoire uploads créé: {UPLOAD_DIR}")
    except Exception as e:
        logger.error(f"❌ Erreur création uploads: {e}")
    
    # Connexion à MongoDB en arrière-plan
    logger.info("🚀 Démarrage du service Content...")
    
    # Lancer la connexion dans un thread séparé
    import threading
    def connect_mongo():
        try:
            connect_to_mongodb()
        except Exception as e:
            logger.error(f"Erreur connexion MongoDB: {e}")
            # Assure que memory_storage est initialisé
            get_memory_storage()
    
    thread = threading.Thread(target=connect_mongo)
    thread.daemon = True
    thread.start()
    
    # Donner un peu de temps pour le message de démarrage
    time.sleep(0.5)

@app.on_event("shutdown")
def shutdown_event():
    """Exécuté à l'arrêt de l'application"""
    global client
    if client is not None:
        try:
            client.close()
            logger.info("🔌 Connexion MongoDB fermée")
        except:
            pass
    logger.info("🛑 Service Content arrêté")

# ========== ENDPOINTS ==========

@app.get("/")
def root():
    mongodb_connected = is_mongodb_connected()
    return {
        "service": "Content Service",
        "version": "2.0.0",
        "database": "mongodb" if mongodb_connected else "memory",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
def health():
    """Health check - CORRIGÉ pour PyMongo"""
    try:
        mongodb_connected = is_mongodb_connected()
        
        if mongodb_connected:
            db_status = "connected"
            service_status = "healthy"
        elif memory_storage is not None:
            db_status = "memory"
            service_status = "healthy"
        else:
            db_status = "initializing"
            service_status = "starting"
        
        return {
            "status": service_status,
            "database": db_status,
            "service": "content-service",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur health check: {e}")
        return {
            "status": "error",
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/config")
def get_config():
    """Afficher la configuration"""
    mongodb_connected = is_mongodb_connected()
    return {
        "mongodb_host": MONGODB_HOST,
        "mongodb_db": MONGODB_DB,
        "upload_dir": UPLOAD_DIR,
        "database_mode": "mongodb" if mongodb_connected else "memory",
        "mongodb_connected": mongodb_connected,
        "host": "0.0.0.0",
        "port": 8001
    }

@app.get("/test")
def test_endpoint():
    """Endpoint de test simple"""
    mongodb_connected = is_mongodb_connected()
    return {
        "message": "Service content opérationnel",
        "database": "mongodb" if mongodb_connected else "memory",
        "mongodb_connected": mongodb_connected,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "ok"
    }

@app.get("/database/ping")
def ping_mongodb():
    """Tester directement la connexion MongoDB"""
    try:
        from pymongo import MongoClient
        
        MONGODB_URL = f"{MONGODB_HOST}/{MONGODB_DB}?authSource=admin"
        
        # Test direct
        test_client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=3000)
        test_client.admin.command('ping')
        test_client.close()
        
        return {
            "status": "success",
            "message": "MongoDB is reachable",
            "url": MONGODB_HOST
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "MongoDB is not reachable",
            "error": str(e),
            "url": MONGODB_HOST
        }

# ========== COURS ENDPOINTS ==========

@app.post("/course")
def create_course(course: CourseCreate):
    """Créer un nouveau cours"""
    try:
        course_data = course.dict()
        course_data["created_at"] = datetime.utcnow()
        course_data["updated_at"] = datetime.utcnow()
        course_data["lesson_count"] = 0
        course_data["quiz_count"] = 0
        
        if is_mongodb_connected():
            try:
                # Insérer dans MongoDB
                result = db.courses.insert_one(course_data)
                course_id = str(result.inserted_id)
                storage = "mongodb"
            except Exception as e:
                logger.error(f"❌ Erreur MongoDB: {e}")
                raise HTTPException(status_code=503, detail="Database unavailable")
        else:
            # Stockage mémoire (fallback)
            storage_obj = get_memory_storage()
            course_id = generate_memory_id()
            course_data["_id"] = course_id
            storage_obj["courses"][course_id] = course_data
            storage = "memory"
        
        logger.info(f"📚 Cours créé: {course.title} (ID: {course_id})")
        
        return {
            "id": course_id,
            "message": "Course created successfully",
            "storage": storage,
            "title": course.title
        }
    except Exception as e:
        logger.error(f"Erreur création cours: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/course")
def get_courses():
    """Lister tous les cours"""
    try:
        if is_mongodb_connected():
            try:
                cursor = db.courses.find().limit(100)
                courses = [mongo_to_dict(course) for course in cursor]
                storage = "mongodb"
            except Exception as e:
                logger.error(f"❌ Erreur MongoDB: {e}")
                courses = []
                storage = "error"
        else:
            storage_obj = get_memory_storage()
            courses = list(storage_obj["courses"].values())
            storage = "memory"
        
        return {
            "courses": courses,
            "total": len(courses),
            "storage": storage
        }
    except Exception as e:
        logger.error(f"Erreur récupération cours: {e}")
        return {
            "courses": [],
            "total": 0,
            "storage": "error",
            "error": str(e)
        }

@app.get("/course/{course_id}")
def get_course(course_id: str):
    """Récupérer un cours spécifique"""
    try:
        if is_mongodb_connected():
            try:
                from bson import ObjectId
                course = db.courses.find_one({"_id": ObjectId(course_id)})
                if not course:
                    raise HTTPException(status_code=404, detail="Course not found")
                return mongo_to_dict(course)
            except Exception as e:
                logger.error(f"Erreur MongoDB: {e}")
                raise HTTPException(status_code=404, detail="Course not found")
        else:
            storage_obj = get_memory_storage()
            course = storage_obj["courses"].get(course_id)
            if not course:
                raise HTTPException(status_code=404, detail="Course not found")
            return course
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération cours: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ========== TRANSFORM ENDPOINT ==========

@app.post("/transform")
def transform_content(request: TransformRequest):
    """Transformer du contenu en micro-leçons - VERSION CORRIGÉE"""
    try:
        content = request.content
        target_duration = request.target_duration
        
        if not content or len(content.strip()) < 10:
            raise HTTPException(status_code=400, detail="Content too short")
        
        logger.info(f"Transforming content: {len(content)} chars, duration: {target_duration}min")
        
        try:
            from nltk.tokenize import sent_tokenize
            
            # Simple transformation pour démo
            sentences = sent_tokenize(content)
            
            micro_lessons = []
            current_lesson = ""
            word_count = 0
            
            # ~200 mots/minute = 1000 mots pour 5 minutes
            target_words = target_duration * 200
            
            for sentence in sentences:
                sentence_words = len(sentence.split())
                
                if word_count + sentence_words > target_words and current_lesson:
                    # Créer une micro-leçon
                    micro_lessons.append({
                        "title": f"Leçon {len(micro_lessons) + 1}",
                        "content": current_lesson.strip(),
                        "estimated_minutes": max(1, round(word_count / 200)),
                        "word_count": word_count,
                        "order": len(micro_lessons) + 1
                    })
                    current_lesson = ""
                    word_count = 0
                
                current_lesson += sentence + " "
                word_count += sentence_words
            
            # Dernière leçon
            if current_lesson:
                micro_lessons.append({
                    "title": f"Leçon {len(micro_lessons) + 1}",
                    "content": current_lesson.strip(),
                    "estimated_minutes": max(1, round(word_count / 200)),
                    "word_count": word_count,
                    "order": len(micro_lessons) + 1
                })
            
            return {
                "success": True,
                "micro_lessons": micro_lessons,
                "total_lessons": len(micro_lessons),
                "total_duration": sum(l["estimated_minutes"] for l in micro_lessons),
                "message": f"Transformed into {len(micro_lessons)} micro-lessons"
            }
            
        except ImportError:
            # Fallback si nltk n'est pas disponible
            words = content.split()
            chunk_size = target_duration * 200
            chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
            
            micro_lessons = []
            for i, chunk in enumerate(chunks):
                micro_lessons.append({
                    "title": f"Leçon {i + 1}",
                    "content": " ".join(chunk),
                    "estimated_minutes": target_duration,
                    "word_count": len(chunk),
                    "order": i + 1
                })
            
            return {
                "success": True,
                "micro_lessons": micro_lessons,
                "total_lessons": len(micro_lessons),
                "total_duration": len(micro_lessons) * target_duration,
                "message": f"Transformed into {len(micro_lessons)} micro-lessons (fallback mode)"
            }
            
    except Exception as e:
        logger.error(f"Erreur transformation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Version alternative avec Form (si vous préférez)
@app.post("/transform-form")
def transform_content_form(
    content: str = Form(...),
    target_duration: int = Form(5)
):
    """Transformer du contenu en micro-leçons (version Form)"""
    request = TransformRequest(content=content, target_duration=target_duration)
    return transform_content(request)

# ========== LESSONS ENDPOINTS ==========

@app.get("/lessons")
def get_lessons(course_id: Optional[str] = None):
    """Lister les leçons (optionnellement par cours)"""
    try:
        if is_mongodb_connected():
            try:
                query = {"course_id": course_id} if course_id else {}
                cursor = db.lessons.find(query).sort("order", 1).limit(100)
                lessons = [mongo_to_dict(lesson) for lesson in cursor]
                storage = "mongodb"
            except Exception as e:
                logger.error(f"❌ Erreur MongoDB: {e}")
                lessons = []
                storage = "error"
        else:
            storage_obj = get_memory_storage()
            if course_id:
                lessons = [l for l in storage_obj["lessons"].values() if l.get("course_id") == course_id]
            else:
                lessons = list(storage_obj["lessons"].values())
            lessons.sort(key=lambda x: x.get("order", 0))
            storage = "memory"
        
        return {
            "lessons": lessons,
            "total": len(lessons),
            "storage": storage,
            "course_filter": course_id
        }
    except Exception as e:
        logger.error(f"Erreur récupération leçons: {e}")
        return {
            "lessons": [],
            "total": 0,
            "storage": "error",
            "error": str(e)
        }

@app.post("/lessons")
def create_lesson(lesson: LessonCreate):
    """Créer une nouvelle leçon"""
    try:
        lesson_data = lesson.dict()
        lesson_data["created_at"] = datetime.utcnow()
        lesson_data["views"] = 0
        
        if is_mongodb_connected():
            try:
                # Vérifier que le cours existe
                from bson import ObjectId
                course = db.courses.find_one({"_id": ObjectId(lesson.course_id)})
                if not course:
                    raise HTTPException(status_code=404, detail="Course not found")
                
                # Insérer la leçon
                result = db.lessons.insert_one(lesson_data)
                lesson_id = str(result.inserted_id)
                
                # Mettre à jour le compteur de leçons du cours
                db.courses.update_one(
                    {"_id": ObjectId(lesson.course_id)},
                    {"$inc": {"lesson_count": 1}}
                )
                
                storage = "mongodb"
            except Exception as e:
                logger.error(f"❌ Erreur MongoDB: {e}")
                raise HTTPException(status_code=503, detail="Database unavailable")
        else:
            # Stockage mémoire (fallback)
            storage_obj = get_memory_storage()
            lesson_id = generate_memory_id()
            lesson_data["_id"] = lesson_id
            storage_obj["lessons"][lesson_id] = lesson_data
            storage = "memory"
        
        return {
            "id": lesson_id,
            "message": "Lesson created successfully",
            "storage": storage,
            "title": lesson.title
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur création leçon: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: str):
    """Récupérer une leçon spécifique"""
    try:
        if is_mongodb_connected():
            try:
                from bson import ObjectId
                lesson = db.lessons.find_one({"_id": ObjectId(lesson_id)})
                if not lesson:
                    raise HTTPException(status_code=404, detail="Lesson not found")
                
                # Incrémenter les vues
                db.lessons.update_one(
                    {"_id": ObjectId(lesson_id)},
                    {"$inc": {"views": 1}}
                )
                
                return mongo_to_dict(lesson)
            except Exception as e:
                logger.error(f"Erreur MongoDB: {e}")
                raise HTTPException(status_code=404, detail="Lesson not found")
        else:
            storage_obj = get_memory_storage()
            lesson = storage_obj["lessons"].get(lesson_id)
            if not lesson:
                raise HTTPException(status_code=404, detail="Lesson not found")
            
            # Incrémenter vues en mémoire
            lesson["views"] = lesson.get("views", 0) + 1
            return lesson
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération leçon: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ========== QUIZ ENDPOINTS ==========

@app.post("/quiz")
def create_quiz(quiz: QuizCreate):
    """Créer un nouveau quiz"""
    try:
        quiz_data = quiz.dict()
        quiz_data["created_at"] = datetime.utcnow()
        quiz_data["attempts"] = 0
        quiz_data["average_score"] = 0.0
        
        if is_mongodb_connected():
            try:
                # Vérifier que le cours existe
                from bson import ObjectId
                course = db.courses.find_one({"_id": ObjectId(quiz.course_id)})
                if not course:
                    raise HTTPException(status_code=404, detail="Course not found")
                
                result = db.quizzes.insert_one(quiz_data)
                quiz_id = str(result.inserted_id)
                
                # Mettre à jour le compteur de quiz du cours
                db.courses.update_one(
                    {"_id": ObjectId(quiz.course_id)},
                    {"$inc": {"quiz_count": 1}}
                )
                
                storage = "mongodb"
            except Exception as e:
                logger.error(f"❌ Erreur MongoDB: {e}")
                raise HTTPException(status_code=503, detail="Database unavailable")
        else:
            # Stockage mémoire (fallback)
            storage_obj = get_memory_storage()
            quiz_id = generate_memory_id()
            quiz_data["_id"] = quiz_id
            storage_obj["quizzes"][quiz_id] = quiz_data
            storage = "memory"
        
        return {
            "id": quiz_id,
            "message": "Quiz created successfully",
            "storage": storage,
            "title": quiz.title,
            "questions": len(quiz.questions)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur création quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quiz")
def get_quizzes(course_id: Optional[str] = None):
    """Lister les quiz (optionnellement par cours)"""
    try:
        if is_mongodb_connected():
            try:
                query = {"course_id": course_id} if course_id else {}
                cursor = db.quizzes.find(query).limit(100)
                quizzes = [mongo_to_dict(quiz) for quiz in cursor]
                storage = "mongodb"
            except Exception as e:
                logger.error(f"❌ Erreur MongoDB: {e}")
                quizzes = []
                storage = "error"
        else:
            storage_obj = get_memory_storage()
            if course_id:
                quizzes = [q for q in storage_obj["quizzes"].values() if q.get("course_id") == course_id]
            else:
                quizzes = list(storage_obj["quizzes"].values())
            storage = "memory"
        
        return {
            "quizzes": quizzes,
            "total": len(quizzes),
            "storage": storage,
            "course_filter": course_id
        }
    except Exception as e:
        logger.error(f"Erreur récupération quiz: {e}")
        return {
            "quizzes": [],
            "total": 0,
            "storage": "error",
            "error": str(e)
        }

@app.get("/quiz/{quiz_id}")
def get_quiz(quiz_id: str):
    """Récupérer un quiz spécifique"""
    try:
        if is_mongodb_connected():
            try:
                from bson import ObjectId
                quiz = db.quizzes.find_one({"_id": ObjectId(quiz_id)})
                if not quiz:
                    raise HTTPException(status_code=404, detail="Quiz not found")
                return mongo_to_dict(quiz)
            except Exception as e:
                logger.error(f"Erreur MongoDB: {e}")
                raise HTTPException(status_code=404, detail="Quiz not found")
        else:
            storage_obj = get_memory_storage()
            quiz = storage_obj["quizzes"].get(quiz_id)
            if not quiz:
                raise HTTPException(status_code=404, detail="Quiz not found")
            return quiz
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération quiz: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ========== STATS ENDPOINT ==========

@app.get("/stats")
def get_stats():
    """Obtenir les statistiques du service"""
    try:
        if is_mongodb_connected():
            try:
                courses_count = db.courses.count_documents({})
                lessons_count = db.lessons.count_documents({})
                quizzes_count = db.quizzes.count_documents({})
                
                # Total des vues de leçons
                pipeline = [{"$group": {"_id": None, "total_views": {"$sum": "$views"}}}]
                views_result = list(db.lessons.aggregate(pipeline))
                total_views = views_result[0]["total_views"] if views_result else 0
                
                storage = "mongodb"
            except Exception as e:
                logger.error(f"Erreur MongoDB stats: {e}")
                courses_count = lessons_count = quizzes_count = total_views = 0
                storage = "error"
        else:
            storage_obj = get_memory_storage()
            courses_count = len(storage_obj["courses"])
            lessons_count = len(storage_obj["lessons"])
            quizzes_count = len(storage_obj["quizzes"])
            total_views = sum(l.get("views", 0) for l in storage_obj["lessons"].values())
            storage = "memory"
        
        return {
            "courses_count": courses_count,
            "lessons_count": lessons_count,
            "quizzes_count": quizzes_count,
            "total_lesson_views": total_views,
            "storage": storage,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur stats: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# ========== DÉMARRAGE ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 CONTENT SERVICE - MICRO LEARNING")
    print("=" * 60)
    print(f"📡 Host: 0.0.0.0")
    print(f"🔌 Port: 8001")
    print(f"📊 MongoDB Host: {MONGODB_HOST}")
    print(f"🗃️  Database: {MONGODB_DB}")
    print(f"📚 Docs: http://localhost:8001/docs")
    print("=" * 60)
    print("📋 Endpoints disponibles:")
    print("  GET  /               - Page d'accueil")
    print("  GET  /health         - Health check")
    print("  GET  /config         - Configuration")
    print("  GET  /database/ping  - Tester MongoDB")
    print("  POST /course         - Créer un cours")
    print("  GET  /course         - Lister les cours")
    print("  GET  /course/{id}    - Récupérer un cours")
    print("  POST /transform      - Transformer du contenu (JSON)")
    print("  POST /transform-form - Transformer (Form)")
    print("  GET  /lessons        - Lister les leçons")
    print("  POST /lessons        - Créer une leçon")
    print("  GET  /lessons/{id}   - Récupérer une leçon")
    print("  POST /quiz           - Créer un quiz")
    print("  GET  /quiz           - Lister les quiz")
    print("  GET  /quiz/{id}      - Récupérer un quiz")
    print("  GET  /stats          - Statistiques")
    print("=" * 60)
    
    # Initialiser memory_storage au cas où
    get_memory_storage()
    
    # Démarrer le service
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8001, 
        log_level="info", 
        access_log=True,
        reload=False
    )