import os
from typing import Optional

class Settings:
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:password@postgres:5432/userdb")
    
    # JWT
    secret_key: str = os.getenv("SECRET_KEY", "development-secret-key-change-in-production")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # App
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    def __init__(self):
        print(f"=== CONFIGURATION ===")
        print(f"Database URL: {self.database_url}")
        print(f"App Port: {self.app_port}")
        print(f"Debug: {self.debug}")
        print(f"=====================")

settings = Settings()