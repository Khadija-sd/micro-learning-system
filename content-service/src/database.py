from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
import logging
from src.config import settings

logger = logging.getLogger(__name__)

# Variables globales
client = None
db = None

def init_db():
    """Initialiser la connexion MongoDB"""
    global client, db
    
    try:
        client = MongoClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=50
        )
        
        # Test connexion
        client.admin.command('ping')
        db = client[settings.MONGODB_DB]
        
        # Créer collections si nécessaire
        collections = ["courses", "lessons", "quizzes", "quiz_submissions"]
        existing = db.list_collection_names()
        
        for collection in collections:
            if collection not in existing:
                db.create_collection(collection)
        
        # Créer indexes
        db.courses.create_index("teacher_id")
        db.courses.create_index("subject")
        db.lessons.create_index("course_id")
        db.lessons.create_index([("course_id", 1), ("order", 1)])
        db.quizzes.create_index("course_id")
        
        logger.info(f"✅ MongoDB initialisé: {settings.MONGODB_DB}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Échec connexion MongoDB: {e}")
        logger.warning("⚠ Utilisation du stockage en mémoire")
        return False

def get_db():
    """Obtenir l'instance de la base de données"""
    return db

def get_client():
    """Obtenir le client MongoDB"""
    return client

# Fonctions utilitaires
def object_id_to_str(doc):
    """Convertir ObjectId en string"""
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc

def str_to_object_id(id_str):
    """Convertir string en ObjectId"""
    try:
        return ObjectId(id_str)
    except:
        return None