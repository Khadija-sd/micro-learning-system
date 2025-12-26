import os
from typing import Optional

class Settings:
    # Application
    APP_NAME: str = "Content Service"
    VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8001))
    
    # MongoDB
    MONGODB_URL: str = os.getenv(
        "MONGODB_URL", 
        "mongodb://admin:password@mongodb:27017/contentdb?authSource=admin"
    )
    MONGODB_DB: str = os.getenv("MONGODB_DB", "contentdb")
    
    # File Processing
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: set = {".pdf", ".txt", ".docx"}
    
    # Text Processing
    MICRO_LESSON_DURATION: int = 5  # minutes
    WORDS_PER_MINUTE: int = 200  # vitesse lecture moyenne
    
    class Config:
        env_file = ".env"

settings = Settings()