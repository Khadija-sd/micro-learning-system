from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
import uvicorn
import logging
from datetime import datetime
import os
import time
import json
import tempfile
import shutil
import re

# Ajout des imports Dapr
from dapr.ext.fastapi import DaprApp
from dapr.clients import DaprClient

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

# ========== MODÈLES AJOUTÉS POUR LES QUIZ ==========
class QuizSubmissionRequest(BaseModel):
    user_id: str
    answers: List[str]

class QuizScoreResponse(BaseModel):
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
    answers_feedback: List[dict]

class QuizAttemptResponse(BaseModel):
    id: str
    quiz_id: str
    user_id: str
    score: int
    percentage: float
    passed: bool
    submitted_at: datetime

class UserQuizStatsResponse(BaseModel):
    user_id: str
    quiz_id: str
    quiz_title: str
    best_score: int
    best_percentage: float
    attempts_count: int
    last_attempt: Optional[datetime]
    average_score: float

# ========== APPLICATION ==========
app = FastAPI(
    title="Content Service - Micro Learning",
    version="2.0.0",
    description="Service de gestion de contenu pédagogique et transformation en micro-leçons",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialisation de Dapr
dapr_app = DaprApp(app)

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

# ========== FONCTIONS AJOUTÉES POUR LES QUIZ ==========
def calculate_quiz_score(quiz: dict, answers: List[str]) -> dict:
    """Calculer le score d'un quiz"""
    try:
        questions = quiz.get("questions", [])
        total_questions = len(questions)
        total_points = sum(q.get("points", 1) for q in questions)
        
        correct_answers = 0
        earned_points = 0
        answers_feedback = []
        
        for i, (question, user_answer) in enumerate(zip(questions, answers)):
            is_correct = user_answer.strip().lower() == question["correct_answer"].strip().lower()
            question_points = question.get("points", 1)
            
            if is_correct:
                correct_answers += 1
                earned_points += question_points
            
            answers_feedback.append({
                "question_index": i,
                "question_text": question["text"],
                "user_answer": user_answer,
                "correct_answer": question["correct_answer"],
                "is_correct": is_correct,
                "points": question_points,
                "earned_points": question_points if is_correct else 0,
                "options": question.get("options", [])
            })
        
        score = earned_points
        percentage = (earned_points / total_points * 100) if total_points > 0 else 0
        passing_score = quiz.get("passing_score", 70)
        passed = percentage >= passing_score
        
        return {
            "score": score,
            "percentage": round(percentage, 2),
            "passed": passed,
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "total_points": total_points,
            "earned_points": earned_points,
            "answers_feedback": answers_feedback
        }
        
    except Exception as e:
        logger.error(f"Erreur calcul score quiz: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur calcul score: {str(e)}")

def update_quiz_statistics(quiz_id: str, score_percentage: float):
    """Mettre à jour les statistiques du quiz"""
    try:
        if is_mongodb_connected():
            from bson import ObjectId
            
            # Récupérer le quiz
            quiz = db.quizzes.find_one({"_id": ObjectId(quiz_id)})
            if not quiz:
                return
            
            # Mettre à jour les statistiques
            attempts = quiz.get("attempts", 0) + 1
            current_avg = quiz.get("average_score", 0.0)
            
            # Nouvelle moyenne = (ancienne moyenne * (n-1) + nouveau score) / n
            new_average = ((current_avg * (attempts - 1)) + score_percentage) / attempts
            
            db.quizzes.update_one(
                {"_id": ObjectId(quiz_id)},
                {
                    "$set": {
                        "attempts": attempts,
                        "average_score": round(new_average, 2),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"📊 Statistiques quiz mises à jour: {quiz_id}, tentatives: {attempts}, moyenne: {new_average:.1f}%")
            
    except Exception as e:
        logger.error(f"Erreur mise à jour statistiques quiz: {e}")

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

# ========== DAPR SUBSCRIPTIONS ==========

# Modifiez temporairement la route
@app.get("/dapr/subscriptions")  # Changez le nom
def subscribe():
    """Retourne les subscriptions Dapr pour ce service"""
    subscriptions = [
        {
            "pubsubname": "pubsub",
            "topic": "quiz_completed",
            "route": "/events/quiz-completed"
        },
        {
            "pubsubname": "pubsub",
            "topic": "course_created", 
            "route": "/events/course-created"
        }
    ]
    logger.info(f"📡 Subscriptions Dapr envoyées: {subscriptions}")
    return subscriptions
# ========== DAPR EVENT HANDLER ==========

@app.post("/events/{event_type}")
async def handle_event(event_type: str, request: dict):
    """Gestionnaire d'événements Dapr"""
    logger.info(f"📨 Événement reçu: {event_type}")
    
    # Afficher les données reçues (formatées)
    logger.debug(f"📦 Données reçues: {json.dumps(request, indent=2)}")
    
    if event_type == "quiz-completed":
        # Traiter l'événement quiz complété
        quiz_id = request.get("quiz_id")
        user_id = request.get("user_id")
        score = request.get("score")
        
        logger.info(f"📝 Quiz {quiz_id} complété par {user_id} avec score {score}")
        
        # Mettre à jour les statistiques ou déclencher d'autres actions
        return {"status": "processed", "event": event_type}
    
    elif event_type == "course-created":
        # Traiter l'événement cours créé
        course_id = request.get("course_id")
        teacher_id = request.get("teacher_id")
        
        logger.info(f"📚 Cours {course_id} créé par professeur {teacher_id}")
        
        # Optionnel: Publier un autre événement
        try:
            dapr_client = DaprClient()
            await dapr_client.publish_event(
                pubsub_name="pubsub",
                topic_name="content_ready",
                data={
                    "course_id": course_id,
                    "message": f"Cours transformé en micro-leçons",
                    "timestamp": datetime.utcnow().isoformat()
                },
                data_content_type='application/json'
            )
            logger.info(f"📤 Événement content_ready publié pour le cours {course_id}")
            
        except Exception as e:
            logger.error(f"❌ Erreur publication événement: {e}")
        
        return {"status": "processed", "event": event_type}
    
    else:
        logger.warning(f"⚠️ Événement non reconnu: {event_type}")
        return {"status": "ignored", "event": event_type, "message": "Event type not recognized"}

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
            
            # Publier un événement Dapr pour notifier la création du cours
            try:
                dapr_client = DaprClient()
                
                await dapr_client.publish_event(
                    pubsub_name="pubsub",
                    topic_name="course_created",
                    data={
                        "course_id": course_id,
                        "teacher_id": teacher_id,
                        "title": title,
                        "subject": subject,
                        "micro_lessons_count": len(lessons_created),
                        "timestamp": datetime.utcnow().isoformat(),
                        "service": "content-service"
                    },
                    data_content_type='application/json'
                )
                
                logger.info(f"📤 Événement publié: course_created pour {course_id}")
                
            except Exception as pub_error:
                logger.error(f"❌ Erreur publication événement Dapr: {pub_error}")
                # Ne pas lever d'exception, continuer avec le résultat
            
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

# ========== ENDPOINTS AJOUTÉS POUR LES QUIZ ==========

@app.post("/quiz/{quiz_id}/submit")
async def submit_quiz_answers(quiz_id: str, submission: QuizSubmissionRequest):
    """Soumettre les réponses d'un quiz et obtenir le score"""
    try:
        logger.info(f"📝 Soumission quiz: {quiz_id} par utilisateur: {submission.user_id}")
        
        if is_mongodb_connected():
            try:
                from bson import ObjectId
                
                # Récupérer le quiz
                quiz = db.quizzes.find_one({"_id": ObjectId(quiz_id)})
                if not quiz:
                    raise HTTPException(status_code=404, detail="Quiz not found")
                
                # Vérifier le nombre de réponses
                questions_count = len(quiz.get("questions", []))
                if len(submission.answers) != questions_count:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Nombre de réponses incorrect. Attendu: {questions_count}, Reçu: {len(submission.answers)}"
                    )
                
                # Calculer le score
                score_result = calculate_quiz_score(quiz, submission.answers)
                
                # Créer l'enregistrement de soumission
                submission_data = {
                    "quiz_id": quiz_id,
                    "user_id": submission.user_id,
                    "answers": submission.answers,
                    "score": score_result["score"],
                    "percentage": score_result["percentage"],
                    "passed": score_result["passed"],
                    "total_questions": score_result["total_questions"],
                    "correct_answers": score_result["correct_answers"],
                    "total_points": score_result["total_points"],
                    "earned_points": score_result["earned_points"],
                    "submitted_at": datetime.utcnow(),
                    "answers_feedback": score_result["answers_feedback"]
                }
                
                # Enregistrer la soumission
                result = db.quiz_submissions.insert_one(submission_data)
                submission_id = str(result.inserted_id)
                
                # Mettre à jour les statistiques du quiz
                update_quiz_statistics(quiz_id, score_result["percentage"])
                
                # Publier un événement Dapr
                try:
                    dapr_client = DaprClient()
                    
                    await dapr_client.publish_event(
                        pubsub_name="pubsub",
                        topic_name="quiz_completed",
                        data={
                            "quiz_id": quiz_id,
                            "user_id": submission.user_id,
                            "score": score_result["score"],
                            "percentage": score_result["percentage"],
                            "passed": score_result["passed"],
                            "total_questions": score_result["total_questions"],
                            "timestamp": datetime.utcnow().isoformat(),
                            "service": "content-service"
                        },
                        data_content_type='application/json'
                    )
                    
                    logger.info(f"📤 Événement publié: quiz_completed pour {quiz_id}")
                    
                except Exception as pub_error:
                    logger.error(f"❌ Erreur publication événement Dapr: {pub_error}")
                    # Ne pas lever d'exception, continuer avec le résultat du quiz
                
                logger.info(f"✅ Quiz soumis: {quiz['title']}, Score: {score_result['score']}/{score_result['total_points']} ({score_result['percentage']}%)")
                
                return {
                    "submission_id": submission_id,
                    "quiz_id": quiz_id,
                    "quiz_title": quiz.get("title", ""),
                    "user_id": submission.user_id,
                    "score": score_result["score"],
                    "percentage": score_result["percentage"],
                    "passed": score_result["passed"],
                    "total_questions": score_result["total_questions"],
                    "correct_answers": score_result["correct_answers"],
                    "total_points": score_result["total_points"],
                    "earned_points": score_result["earned_points"],
                    "submitted_at": submission_data["submitted_at"],
                    "message": "Quiz submitted successfully"
                }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Erreur soumission quiz: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        else:
            # Mode mémoire
            storage_obj = get_memory_storage()
            
            # Récupérer le quiz
            quiz = None
            for q_id, q in storage_obj["quizzes"].items():
                if q_id == quiz_id:
                    quiz = q
                    break
            
            if not quiz:
                raise HTTPException(status_code=404, detail="Quiz not found")
            
            # Calculer le score
            score_result = calculate_quiz_score(quiz, submission.answers)
            
            # Créer l'enregistrement de soumission
            submission_id = generate_memory_id()
            submission_data = {
                "_id": submission_id,
                "quiz_id": quiz_id,
                "user_id": submission.user_id,
                "answers": submission.answers,
                "score": score_result["score"],
                "percentage": score_result["percentage"],
                "passed": score_result["passed"],
                "total_questions": score_result["total_questions"],
                "correct_answers": score_result["correct_answers"],
                "total_points": score_result["total_points"],
                "earned_points": score_result["earned_points"],
                "submitted_at": datetime.utcnow(),
                "answers_feedback": score_result["answers_feedback"]
            }
            
            # Enregistrer la soumission
            storage_obj["quiz_submissions"].append(submission_data)
            
            # Mettre à jour les statistiques du quiz
            if quiz_id in storage_obj["quizzes"]:
                quiz_obj = storage_obj["quizzes"][quiz_id]
                attempts = quiz_obj.get("attempts", 0) + 1
                current_avg = quiz_obj.get("average_score", 0.0)
                new_average = ((current_avg * (attempts - 1)) + score_result["percentage"]) / attempts
                
                quiz_obj["attempts"] = attempts
                quiz_obj["average_score"] = round(new_average, 2)
                quiz_obj["updated_at"] = datetime.utcnow()
            
            return {
                "submission_id": submission_id,
                "quiz_id": quiz_id,
                "quiz_title": quiz.get("title", ""),
                "user_id": submission.user_id,
                "score": score_result["score"],
                "percentage": score_result["percentage"],
                "passed": score_result["passed"],
                "total_questions": score_result["total_questions"],
                "correct_answers": score_result["correct_answers"],
                "total_points": score_result["total_points"],
                "earned_points": score_result["earned_points"],
                "submitted_at": submission_data["submitted_at"],
                "message": "Quiz submitted successfully (memory mode)"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur soumission quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quiz/{quiz_id}/results/{user_id}")
def get_user_quiz_results(quiz_id: str, user_id: str):
    """Obtenir les résultats d'un utilisateur pour un quiz spécifique"""
    try:
        logger.info(f"📊 Récupération résultats quiz: {quiz_id} pour utilisateur: {user_id}")
        
        if is_mongodb_connected():
            try:
                from bson import ObjectId
                
                # Récupérer toutes les soumissions de l'utilisateur pour ce quiz
                submissions = list(db.quiz_submissions.find({
                    "quiz_id": quiz_id,
                    "user_id": user_id
                }).sort("submitted_at", -1))
                
                if not submissions:
                    raise HTTPException(
                        status_code=404,
                        detail="No submissions found for this user and quiz"
                    )
                
                # Récupérer les infos du quiz
                quiz = db.quizzes.find_one({"_id": ObjectId(quiz_id)})
                
                # Calculer les statistiques
                best_submission = max(submissions, key=lambda x: x.get("percentage", 0))
                total_attempts = len(submissions)
                average_score = sum(s.get("percentage", 0) for s in submissions) / total_attempts
                
                return {
                    "user_id": user_id,
                    "quiz_id": quiz_id,
                    "quiz_title": quiz.get("title", "") if quiz else "Unknown Quiz",
                    "total_attempts": total_attempts,
                    "best_score": best_submission.get("score", 0),
                    "best_percentage": best_submission.get("percentage", 0),
                    "average_score": round(average_score, 2),
                    "last_attempt": best_submission.get("submitted_at"),
                    "submissions": [
                        {
                            "submission_id": str(s.get("_id", "")),
                            "score": s.get("score", 0),
                            "percentage": s.get("percentage", 0),
                            "passed": s.get("passed", False),
                            "submitted_at": s.get("submitted_at"),
                            "correct_answers": s.get("correct_answers", 0),
                            "total_questions": s.get("total_questions", 0)
                        }
                        for s in submissions[:10]  # Limiter à 10 dernières soumissions
                    ]
                }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Erreur récupération résultats: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        else:
            # Mode mémoire
            storage_obj = get_memory_storage()
            
            # Récupérer les soumissions
            submissions = [
                s for s in storage_obj["quiz_submissions"]
                if s.get("quiz_id") == quiz_id and s.get("user_id") == user_id
            ]
            
            if not submissions:
                raise HTTPException(
                    status_code=404,
                    detail="No submissions found for this user and quiz"
                )
            
            # Récupérer les infos du quiz
            quiz = storage_obj["quizzes"].get(quiz_id, {})
            
            # Calculer les statistiques
            best_submission = max(submissions, key=lambda x: x.get("percentage", 0))
            total_attempts = len(submissions)
            average_score = sum(s.get("percentage", 0) for s in submissions) / total_attempts
            
            return {
                "user_id": user_id,
                "quiz_id": quiz_id,
                "quiz_title": quiz.get("title", "Unknown Quiz"),
                "total_attempts": total_attempts,
                "best_score": best_submission.get("score", 0),
                "best_percentage": best_submission.get("percentage", 0),
                "average_score": round(average_score, 2),
                "last_attempt": best_submission.get("submitted_at"),
                "submissions": [
                    {
                        "submission_id": s.get("_id", ""),
                        "score": s.get("score", 0),
                        "percentage": s.get("percentage", 0),
                        "passed": s.get("passed", False),
                        "submitted_at": s.get("submitted_at"),
                        "correct_answers": s.get("correct_answers", 0),
                        "total_questions": s.get("total_questions", 0)
                    }
                    for s in submissions[:10]
                ]
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur récupération résultats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/user/{user_id}/quiz-stats")
def get_user_quiz_statistics(user_id: str, limit: int = 10):
    """Obtenir les statistiques de quiz d'un utilisateur"""
    try:
        logger.info(f"📈 Récupération statistiques quiz pour utilisateur: {user_id}")
        
        if is_mongodb_connected():
            try:
                # Récupérer toutes les soumissions de l'utilisateur
                submissions = list(db.quiz_submissions.find({
                    "user_id": user_id
                }).sort("submitted_at", -1))
                
                if not submissions:
                    return {
                        "user_id": user_id,
                        "total_quizzes_taken": 0,
                        "total_attempts": 0,
                        "average_score": 0,
                        "passed_quizzes": 0,
                        "quiz_stats": []
                    }
                
                # Grouper par quiz
                quiz_stats = {}
                for submission in submissions:
                    quiz_id = submission.get("quiz_id")
                    
                    if quiz_id not in quiz_stats:
                        # Récupérer les infos du quiz
                        try:
                            from bson import ObjectId
                            quiz = db.quizzes.find_one({"_id": ObjectId(quiz_id)})
                            quiz_title = quiz.get("title", "Unknown Quiz") if quiz else "Unknown Quiz"
                        except:
                            quiz_title = "Unknown Quiz"
                        
                        quiz_stats[quiz_id] = {
                            "quiz_id": quiz_id,
                            "quiz_title": quiz_title,
                            "attempts": [],
                            "best_score": 0,
                            "best_percentage": 0,
                            "last_attempt": None
                        }
                    
                    quiz_stats[quiz_id]["attempts"].append(submission.get("percentage", 0))
                    
                    # Mettre à jour le meilleur score
                    current_percentage = submission.get("percentage", 0)
                    if current_percentage > quiz_stats[quiz_id]["best_percentage"]:
                        quiz_stats[quiz_id]["best_percentage"] = current_percentage
                        quiz_stats[quiz_id]["best_score"] = submission.get("score", 0)
                    
                    # Mettre à jour la dernière tentative
                    current_date = submission.get("submitted_at")
                    if not quiz_stats[quiz_id]["last_attempt"] or current_date > quiz_stats[quiz_id]["last_attempt"]:
                        quiz_stats[quiz_id]["last_attempt"] = current_date
                
                # Calculer les statistiques globales
                total_quizzes_taken = len(quiz_stats)
                total_attempts = len(submissions)
                all_percentages = [s.get("percentage", 0) for s in submissions]
                average_score = sum(all_percentages) / total_attempts if total_attempts > 0 else 0
                passed_attempts = sum(1 for s in submissions if s.get("passed", False))
                
                # Préparer la réponse
                stats_list = []
                for quiz_id, stats in list(quiz_stats.items())[:limit]:
                    attempts_count = len(stats["attempts"])
                    avg_quiz_score = sum(stats["attempts"]) / attempts_count if attempts_count > 0 else 0
                    
                    stats_list.append({
                        "quiz_id": quiz_id,
                        "quiz_title": stats["quiz_title"],
                        "attempts_count": attempts_count,
                        "best_score": stats["best_score"],
                        "best_percentage": stats["best_percentage"],
                        "average_score": round(avg_quiz_score, 2),
                        "last_attempt": stats["last_attempt"]
                    })
                
                return {
                    "user_id": user_id,
                    "total_quizzes_taken": total_quizzes_taken,
                    "total_attempts": total_attempts,
                    "average_score": round(average_score, 2),
                    "passed_quizzes": passed_attempts,
                    "pass_rate": round((passed_attempts / total_attempts * 100), 2) if total_attempts > 0 else 0,
                    "quiz_stats": stats_list
                }
                
            except Exception as e:
                logger.error(f"❌ Erreur récupération statistiques: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        else:
            # Mode mémoire
            storage_obj = get_memory_storage()
            
            # Récupérer les soumissions
            submissions = [
                s for s in storage_obj["quiz_submissions"]
                if s.get("user_id") == user_id
            ]
            
            if not submissions:
                return {
                    "user_id": user_id,
                    "total_quizzes_taken": 0,
                    "total_attempts": 0,
                    "average_score": 0,
                    "passed_quizzes": 0,
                    "quiz_stats": []
                }
            
            # Grouper par quiz (logique similaire à MongoDB)
            # ... (implémentation similaire pour le mode mémoire)
            
            return {
                "user_id": user_id,
                "total_quizzes_taken": 0,
                "total_attempts": 0,
                "average_score": 0,
                "passed_quizzes": 0,
                "message": "Statistics not implemented in memory mode"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur récupération statistiques: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quiz/{quiz_id}/leaderboard")
def get_quiz_leaderboard(quiz_id: str, top_n: int = 10):
    """Obtenir le classement pour un quiz"""
    try:
        logger.info(f"🏆 Récupération classement quiz: {quiz_id}")
        
        if is_mongodb_connected():
            try:
                # Pipeline d'agrégation pour obtenir les meilleurs scores par utilisateur
                pipeline = [
                    {"$match": {"quiz_id": quiz_id}},
                    {"$sort": {"percentage": -1, "submitted_at": -1}},
                    {"$group": {
                        "_id": "$user_id",
                        "best_score": {"$first": "$score"},
                        "best_percentage": {"$first": "$percentage"},
                        "last_attempt": {"$first": "$submitted_at"},
                        "attempts_count": {"$sum": 1}
                    }},
                    {"$sort": {"best_percentage": -1}},
                    {"$limit": top_n}
                ]
                
                results = list(db.quiz_submissions.aggregate(pipeline))
                
                # Récupérer les infos du quiz
                from bson import ObjectId
                quiz = db.quizzes.find_one({"_id": ObjectId(quiz_id)})
                
                leaderboard = []
                for i, result in enumerate(results):
                    leaderboard.append({
                        "rank": i + 1,
                        "user_id": result["_id"],
                        "score": result["best_score"],
                        "percentage": result["best_percentage"],
                        "last_attempt": result["last_attempt"],
                        "attempts_count": result["attempts_count"]
                    })
                
                return {
                    "quiz_id": quiz_id,
                    "quiz_title": quiz.get("title", "") if quiz else "Unknown Quiz",
                    "total_participants": len(results),
                    "leaderboard": leaderboard
                }
                
            except Exception as e:
                logger.error(f"❌ Erreur récupération classement: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        else:
            return {
                "quiz_id": quiz_id,
                "message": "Leaderboard not implemented in memory mode"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur récupération classement: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
                quiz_submissions_count = db.quiz_submissions.count_documents({})
                
                # Total des vues de leçons
                pipeline = [{"$group": {"_id": None, "total_views": {"$sum": "$views"}}}]
                views_result = list(db.lessons.aggregate(pipeline))
                total_views = views_result[0]["total_views"] if views_result else 0
                
                # Statistiques des quiz
                quiz_pipeline = [
                    {"$group": {
                        "_id": None,
                        "total_attempts": {"$sum": "$attempts"},
                        "avg_score": {"$avg": "$average_score"}
                    }}
                ]
                quiz_stats_result = list(db.quizzes.aggregate(quiz_pipeline))
                total_quiz_attempts = quiz_stats_result[0]["total_attempts"] if quiz_stats_result else 0
                avg_quiz_score = quiz_stats_result[0]["avg_score"] if quiz_stats_result else 0
                
                storage = "mongodb"
            except Exception as e:
                logger.error(f"Erreur MongoDB stats: {e}")
                courses_count = lessons_count = micro_lessons_count = quizzes_count = uploads_count = quiz_submissions_count = total_views = total_quiz_attempts = avg_quiz_score = 0
                storage = "error"
        else:
            storage_obj = get_memory_storage()
            courses_count = len(storage_obj["courses"])
            lessons_count = len(storage_obj["lessons"])
            micro_lessons_count = len([l for l in storage_obj["lessons"].values() if l.get("is_micro_lesson", False)])
            quizzes_count = len(storage_obj["quizzes"])
            uploads_count = len(storage_obj["uploads"])
            quiz_submissions_count = len(storage_obj["quiz_submissions"])
            total_views = sum(l.get("views", 0) for l in storage_obj["lessons"].values())
            total_quiz_attempts = sum(q.get("attempts", 0) for q in storage_obj["quizzes"].values())
            avg_quiz_score = sum(q.get("average_score", 0) for q in storage_obj["quizzes"].values()) / quizzes_count if quizzes_count > 0 else 0
            storage = "memory"
        
        ratio = (micro_lessons_count/lessons_count*100) if lessons_count > 0 else 0
        
        return {
            "courses_count": courses_count,
            "lessons_count": lessons_count,
            "micro_lessons_count": micro_lessons_count,
            "quizzes_count": quizzes_count,
            "uploads_count": uploads_count,
            "quiz_submissions_count": quiz_submissions_count,
            "total_lesson_views": total_views,
            "total_quiz_attempts": total_quiz_attempts,
            "average_quiz_score": round(avg_quiz_score, 2),
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
    print("  POST /quiz/{id}/submit - Soumettre un quiz")
    print("  GET  /quiz/{id}/results/{user_id} - Voir résultats")
    print("  GET  /user/{id}/quiz-stats - Statistiques utilisateur")
    print("  GET  /quiz/{id}/leaderboard - Classement du quiz")
    print("  GET  /stats         - Statistiques micro-learning")
    print("  GET  /health        - Health check")
    print("  GET  /dapr/subscribe - Subscriptions Dapr")
    print("  POST /events/{type} - Gestionnaire d'événements Dapr")
    print("=" * 60)
    print("🎯 Micro-learning features:")
    print("  • Upload automatique PDF/TXT → micro-leçons")
    print("  • Découpage intelligent (NLTK)")
    print("  • Durée optimisée (5 min par défaut)")
    print("  • Détection automatique micro-leçons")
    print("  • Création et passage de quiz")
    print("  • Suivi des scores et statistiques")
    print("  • Classement des participants")
    print("  • Statistiques dédiées")
    print("=" * 60)
    print("🔌 Dapr integration:")
    print("  • Publication événements quiz_completed")
    print("  • Publication événements course_created")
    print("  • Réception événements via /events/{type}")
    print("  • Auto-subscription via /dapr/subscribe")
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