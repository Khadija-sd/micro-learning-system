from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
import uvicorn
import logging
from datetime import datetime
import os
import time
import sys
import tempfile
import shutil
import re

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
            collections = ["courses", "lessons", "quizzes", "quiz_submissions", "uploads"]
            
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
        "uploads": [],
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

class UploadResponse(BaseModel):
    success: bool
    message: str
    course_id: Optional[str] = None
    micro_lessons_created: int = 0
    transformation: Optional[dict] = None

# ========== APPLICATION ==========
app = FastAPI(
    title="Content Service - Micro Learning",
    version="2.0.0",
    description="Service de gestion de contenu pédagogique et transformation en micro-leçons",
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
            "uploads": [],
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

def extract_text_from_file(file_path: str, file_type: str) -> str:
    """Extraire le texte d'un fichier selon son type"""
    try:
        if file_type == "text/plain":
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        
        elif file_type == "application/pdf":
            try:
                # Utiliser pypdf (version 3.x)
                from pypdf import PdfReader
                
                logger.info(f"📖 Extraction PDF avec pypdf: {file_path}")
                text = ""
                
                with open(file_path, 'rb') as f:
                    try:
                        pdf_reader = PdfReader(f)
                        num_pages = len(pdf_reader.pages)
                        logger.info(f"📄 PDF a {num_pages} pages")
                        
                        for page_num in range(num_pages):
                            try:
                                page = pdf_reader.pages[page_num]
                                page_text = page.extract_text()
                                
                                if page_text:
                                    # Nettoyer le texte
                                    page_text = re.sub(r'\s+', ' ', page_text)  # Remplacer multi-espaces
                                    page_text = page_text.strip()
                                    text += page_text + "\n\n"
                                    
                                    logger.debug(f"Page {page_num + 1}: {len(page_text)} caractères")
                                else:
                                    logger.warning(f"Page {page_num + 1}: pas de texte extrait")
                            except Exception as page_error:
                                logger.warning(f"Erreur page {page_num + 1}: {page_error}")
                                continue
                    except Exception as read_error:
                        logger.error(f"Erreur lecture PDF: {read_error}")
                        return f"Erreur lecture PDF: {read_error}"
                
                if not text.strip():
                    logger.warning("⚠️  Aucun texte extrait du PDF")
                    return "Aucun texte extrait du PDF. Le PDF peut être numérisé ou protégé."
                
                logger.info(f"✅ Texte extrait: {len(text)} caractères, {len(text.split())} mots")
                return text
                
            except ImportError as import_error:
                logger.error(f"❌ pypdf n'est pas installé: {import_error}")
                return "Bibliothèque pypdf requise pour extraire le texte des PDFs. Installez avec: pip install pypdf"
            except Exception as e:
                logger.error(f"❌ Erreur extraction PDF: {e}")
                return f"Erreur extraction PDF: {str(e)}"
        
        else:
            raise ValueError(f"Type de fichier non supporté: {file_type}")
            
    except Exception as e:
        logger.error(f"❌ Erreur extraction texte: {e}")
        return f"Erreur extraction texte: {str(e)}"

def clean_text_for_processing(text: str) -> str:
    """Nettoyer le texte avant transformation"""
    # Remplacer les retours à la ligne multiples
    text = re.sub(r'\n+', '\n', text)
    # Remplacer les espaces multiples
    text = re.sub(r' +', ' ', text)
    # Supprimer les caractères de contrôle
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
    # Supprimer les caractères Unicode problématiques
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e]', '', text)
    return text.strip()

def transform_content_internal(content: str, target_duration: int = 5):
    """Fonction interne de transformation"""
    try:
        # Nettoyer le contenu
        content = clean_text_for_processing(content)
        
        if not content or len(content.strip()) < 10:
            raise ValueError("Contenu trop court ou vide")
        
        logger.info(f"🔄 Transformation contenu: {len(content)} caractères, {len(content.split())} mots, durée cible: {target_duration}min")
        
        try:
            from nltk.tokenize import sent_tokenize
            
            # Télécharger les ressources NLTK si nécessaire
            try:
                import nltk
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                logger.info("📥 Téléchargement des ressources NLTK...")
                nltk.download('punkt', quiet=True)
            
            # Tokenizer les phrases
            sentences = sent_tokenize(content)
            logger.info(f"📝 {len(sentences)} phrases détectées")
            
            micro_lessons = []
            current_lesson = ""
            word_count = 0
            
            # ~200 mots/minute = 1000 mots pour 5 minutes
            target_words = target_duration * 200
            
            for sentence in sentences:
                sentence_words = len(sentence.split())
                
                if word_count + sentence_words > target_words and current_lesson:
                    # Créer une micro-leçon
                    lesson_num = len(micro_lessons) + 1
                    lesson_title = f"Micro-leçon {lesson_num}"
                    
                    # Essayer d'extraire un titre du contenu
                    if lesson_num == 1 and len(current_lesson.split()) > 50:
                        # Prendre les premiers 10 mots comme titre potentiel
                        first_words = current_lesson.split()[:10]
                        if len(first_words) >= 3:
                            lesson_title = " ".join(first_words) + "..."
                    
                    micro_lessons.append({
                        "title": lesson_title,
                        "content": current_lesson.strip(),
                        "estimated_minutes": max(1, min(target_duration, round(word_count / 200))),
                        "word_count": word_count,
                        "order": lesson_num
                    })
                    current_lesson = ""
                    word_count = 0
                
                current_lesson += sentence + " "
                word_count += sentence_words
            
            # Dernière leçon
            if current_lesson:
                lesson_num = len(micro_lessons) + 1
                micro_lessons.append({
                    "title": f"Micro-leçon {lesson_num}",
                    "content": current_lesson.strip(),
                    "estimated_minutes": max(1, round(word_count / 200)),
                    "word_count": word_count,
                    "order": lesson_num
                })
            
            # Si le contenu est court, créer une seule leçon avec résumé
            if len(micro_lessons) == 1 and len(content.split()) < 500:
                micro_lessons[0]["title"] = "Résumé complet"
                micro_lessons[0]["is_summary"] = True
            
            logger.info(f"✅ Transformé en {len(micro_lessons)} micro-leçons")
            
            return {
                "success": True,
                "micro_lessons": micro_lessons,
                "total_lessons": len(micro_lessons),
                "total_duration": sum(l["estimated_minutes"] for l in micro_lessons),
                "total_words": sum(l["word_count"] for l in micro_lessons),
                "message": f"Transformé en {len(micro_lessons)} micro-leçons"
            }
            
        except ImportError as nltk_error:
            logger.warning(f"NLTK non disponible: {nltk_error}, utilisation du mode fallback")
            # Fallback si nltk n'est pas disponible
            words = content.split()
            chunk_size = target_duration * 200
            chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
            
            micro_lessons = []
            for i, chunk in enumerate(chunks):
                lesson_title = f"Micro-leçon {i + 1}"
                if i == 0 and len(chunk) > 10:
                    # Prendre les premiers mots comme titre
                    lesson_title = " ".join(chunk[:5]) + "..."
                
                micro_lessons.append({
                    "title": lesson_title,
                    "content": " ".join(chunk),
                    "estimated_minutes": target_duration,
                    "word_count": len(chunk),
                    "order": i + 1
                })
            
            logger.info(f"✅ Transformé en {len(micro_lessons)} micro-leçons (fallback mode)")
            
            return {
                "success": True,
                "micro_lessons": micro_lessons,
                "total_lessons": len(micro_lessons),
                "total_duration": len(micro_lessons) * target_duration,
                "total_words": sum(l["word_count"] for l in micro_lessons),
                "message": f"Transformé en {len(micro_lessons)} micro-leçons (mode fallback)"
            }
            
    except Exception as e:
        logger.error(f"❌ Erreur transformation: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur transformation: {str(e)}")

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
        "service": "Content Service - Micro Learning",
        "version": "2.0.0",
        "database": "mongodb" if mongodb_connected else "memory",
        "status": "running",
        "micro_learning": True,
        "upload_supported": True,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
def health():
    """Health check"""
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
            "micro_learning": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur health check: {e}")
        return {
            "status": "error",
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }

# ========== UPLOAD ENDPOINT ==========

@app.post("/upload", response_model=UploadResponse)
async def upload_and_transform_course(
    file: UploadFile = File(...),
    title: str = Form(...),
    teacher_id: str = Form(...),
    subject: str = Form(...),
    description: Optional[str] = Form(None),
    tags: str = Form(""),
    target_duration: int = Form(5, ge=1, le=30)
):
    """
    Upload un cours (PDF/TXT) et le transforme automatiquement en micro-leçons
    """
    try:
        logger.info(f"📤 Upload cours: {title} par {teacher_id}")
        
        # Vérifier le type de fichier
        allowed_types = ["text/plain", "application/pdf"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Type de fichier non supporté. Utilisez: {', '.join(allowed_types)}"
            )
        
        # Sauvegarder le fichier temporairement
        temp_file = None
        try:
            # Créer un fichier temporaire
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}")
            
            # Écrire le contenu
            content_bytes = await file.read()
            temp_file.write(content_bytes)
            temp_file.close()
            
            # Extraire le texte du fichier
            logger.info(f"📄 Extraction texte depuis: {file.filename}")
            text_content = extract_text_from_file(temp_file.name, file.content_type)
            
            # Vérifier si l'extraction a échoué
            if text_content.startswith("Erreur") or text_content.startswith("Aucun texte"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Échec de l'extraction du texte: {text_content}"
                )
            
            if not text_content or len(text_content.strip()) < 50:
                raise HTTPException(
                    status_code=400,
                    detail="Le fichier est vide ou ne contient pas assez de texte"
                )
            
            # Créer le cours dans la base
            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            
            course_data = {
                "title": title,
                "description": description,
                "teacher_id": teacher_id,
                "subject": subject,
                "tags": tags_list,
                "status": "published",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "lesson_count": 0,
                "quiz_count": 0,
                "original_filename": file.filename,
                "file_type": file.content_type,
                "file_size": len(content_bytes)
            }
            
            if is_mongodb_connected():
                # Sauvegarder dans MongoDB
                result = db.courses.insert_one(course_data)
                course_id = str(result.inserted_id)
                
                # Sauvegarder les métadonnées d'upload
                upload_data = {
                    "course_id": course_id,
                    "filename": file.filename,
                    "file_type": file.content_type,
                    "file_size": len(content_bytes),
                    "uploaded_at": datetime.utcnow(),
                    "teacher_id": teacher_id
                }
                db.uploads.insert_one(upload_data)
                
                storage = "mongodb"
            else:
                # Mode mémoire
                storage_obj = get_memory_storage()
                course_id = generate_memory_id()
                course_data["_id"] = course_id
                storage_obj["courses"][course_id] = course_data
                
                upload_data = {
                    "_id": generate_memory_id(),
                    "course_id": course_id,
                    "filename": file.filename,
                    "file_type": file.content_type,
                    "file_size": len(content_bytes),
                    "uploaded_at": datetime.utcnow(),
                    "teacher_id": teacher_id
                }
                storage_obj["uploads"].append(upload_data)
                
                storage = "memory"
            
            # Transformer le contenu en micro-leçons
            logger.info(f"🔄 Transformation en micro-leçons de {target_duration}min")
            transform_result = transform_content_internal(text_content, target_duration)
            
            # Créer les micro-leçons dans la base
            lessons_created = []
            for i, micro_lesson in enumerate(transform_result["micro_lessons"]):
                lesson_data = {
                    "course_id": course_id,
                    "title": micro_lesson["title"],
                    "content": micro_lesson["content"],
                    "duration_minutes": micro_lesson["estimated_minutes"],
                    "order": i + 1,
                    "tags": tags_list,
                    "created_at": datetime.utcnow(),
                    "views": 0,
                    "word_count": micro_lesson.get("word_count", 0),
                    "is_micro_lesson": True,
                    "source_file": file.filename
                }
                
                if is_mongodb_connected():
                    # Insérer la leçon
                    lesson_result = db.lessons.insert_one(lesson_data)
                    lesson_id = str(lesson_result.inserted_id)
                    
                    # Mettre à jour le compteur de leçons du cours
                    from bson import ObjectId
                    db.courses.update_one(
                        {"_id": ObjectId(course_id)},
                        {"$inc": {"lesson_count": 1}}
                    )
                else:
                    # Mode mémoire
                    storage_obj = get_memory_storage()
                    lesson_id = generate_memory_id()
                    lesson_data["_id"] = lesson_id
                    storage_obj["lessons"][lesson_id] = lesson_data
                    
                    # Mettre à jour le compteur de leçons
                    if course_id in storage_obj["courses"]:
                        storage_obj["courses"][course_id]["lesson_count"] = \
                            storage_obj["courses"][course_id].get("lesson_count", 0) + 1
                
                lessons_created.append(lesson_id)
            
            logger.info(f"✅ Upload réussi: {len(lessons_created)} micro-leçons créées")
            
            return {
                "success": True,
                "message": f"Cours uploadé et transformé en {len(lessons_created)} micro-leçons",
                "course_id": course_id,
                "micro_lessons_created": len(lessons_created),
                "transformation": transform_result
            }
            
        finally:
            # Nettoyer le fichier temporaire
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur upload: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du traitement du fichier: {str(e)}"
        )

# ========== TRANSFORM ENDPOINT ==========

@app.post("/transform")
def transform_content(request: TransformRequest):
    """Transformer du contenu en micro-leçons"""
    return transform_content_internal(request.content, request.target_duration)

@app.post("/transform-micro")
def transform_to_micro(content: str = Form(...)):
    """Transformer en micro-leçons de 5 minutes (durée fixe pour micro-learning)"""
    return transform_content_internal(content, 5)

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

# ========== LESSONS ENDPOINTS ==========

@app.get("/lessons")
def get_lessons(course_id: Optional[str] = None, micro_only: bool = False):
    """Lister les leçons (optionnellement par cours)"""
    try:
        if is_mongodb_connected():
            try:
                query = {"course_id": course_id} if course_id else {}
                if micro_only:
                    query["is_micro_lesson"] = True
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
            
            if micro_only:
                lessons = [l for l in lessons if l.get("is_micro_lesson", False)]
            
            lessons.sort(key=lambda x: x.get("order", 0))
            storage = "memory"
        
        micro_lessons = [l for l in lessons if l.get("is_micro_lesson", False)]
        
        return {
            "lessons": lessons,
            "total": len(lessons),
            "micro_lessons": len(micro_lessons),
            "storage": storage,
            "course_filter": course_id,
            "micro_only": micro_only
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
        lesson_data["is_micro_lesson"] = lesson_data.get("duration_minutes", 5) <= 10
        
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
        
        lesson_type = "micro-leçon" if lesson_data["is_micro_lesson"] else "leçon"
        logger.info(f"📝 {lesson_type} créée: {lesson.title}")
        
        return {
            "id": lesson_id,
            "message": f"{lesson_type.capitalize()} created successfully",
            "storage": storage,
            "title": lesson.title,
            "is_micro_lesson": lesson_data["is_micro_lesson"]
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

# ========== STATS ENDPOINT ==========

@app.get("/stats")
def get_stats():
    """Obtenir les statistiques du service"""
    try:
        if is_mongodb_connected():
            try:
                courses_count = db.courses.count_documents({})
                lessons_count = db.lessons.count_documents({})
                micro_lessons_count = db.lessons.count_documents({"is_micro_lesson": True})
                quizzes_count = db.quizzes.count_documents({})
                uploads_count = db.uploads.count_documents({})
                
                # Total des vues de leçons
                pipeline = [{"$group": {"_id": None, "total_views": {"$sum": "$views"}}}]
                views_result = list(db.lessons.aggregate(pipeline))
                total_views = views_result[0]["total_views"] if views_result else 0
                
                storage = "mongodb"
            except Exception as e:
                logger.error(f"Erreur MongoDB stats: {e}")
                courses_count = lessons_count = micro_lessons_count = quizzes_count = uploads_count = total_views = 0
                storage = "error"
        else:
            storage_obj = get_memory_storage()
            courses_count = len(storage_obj["courses"])
            lessons_count = len(storage_obj["lessons"])
            micro_lessons_count = len([l for l in storage_obj["lessons"].values() if l.get("is_micro_lesson", False)])
            quizzes_count = len(storage_obj["quizzes"])
            uploads_count = len(storage_obj["uploads"])
            total_views = sum(l.get("views", 0) for l in storage_obj["lessons"].values())
            storage = "memory"
        
        ratio = (micro_lessons_count/lessons_count*100) if lessons_count > 0 else 0
        
        return {
            "courses_count": courses_count,
            "lessons_count": lessons_count,
            "micro_lessons_count": micro_lessons_count,
            "quizzes_count": quizzes_count,
            "uploads_count": uploads_count,
            "total_lesson_views": total_views,
            "micro_learning_ratio": f"{ratio:.1f}%",
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
    print(f"📁 Upload Directory: {UPLOAD_DIR}")
    print(f"📚 Docs: http://localhost:8001/docs")
    print("=" * 60)
    print("📋 Endpoints disponibles:")
    print("  POST /upload        - Upload cours (PDF/TXT) → micro-leçons")
    print("  POST /transform     - Transformer texte → micro-leçons")
    print("  POST /transform-micro - Transformer (5min fixe)")
    print("  POST /course        - Créer un cours manuellement")
    print("  GET  /course        - Lister les cours")
    print("  GET  /course/{id}   - Récupérer un cours")
    print("  GET  /lessons       - Lister les leçons")
    print("  POST /lessons       - Créer une leçon/micro-leçon")
    print("  GET  /lessons/{id}  - Récupérer une leçon")
    print("  POST /quiz          - Créer un quiz")
    print("  GET  /quiz          - Lister les quiz")
    print("  GET  /stats         - Statistiques micro-learning")
    print("  GET  /health        - Health check")
    print("=" * 60)
    print("🎯 Micro-learning features:")
    print("  • Upload automatique PDF/TXT → micro-leçons")
    print("  • Découpage intelligent (NLTK)")
    print("  • Durée optimisée (5 min par défaut)")
    print("  • Détection automatique micro-leçons")
    print("  • Statistiques dédiées")
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