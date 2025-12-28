import os
from typing import Set


class Settings:
    # =====================
    # Application
    # =====================
    APP_NAME: str = os.getenv("APP_NAME", "Content Service")
    VERSION: str = os.getenv("VERSION", "2.0.0")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # =====================
    # Server
    # =====================
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8001))

    # =====================
    # Dapr Configuration
    # =====================
    APP_ID: str = os.getenv("APP_ID", "content-service")
    APP_PORT: int = int(os.getenv("APP_PORT", 8001))
    DAPR_HTTP_PORT: int = int(os.getenv("DAPR_HTTP_PORT", 3500))
    DAPR_GRPC_PORT: int = int(os.getenv("DAPR_GRPC_PORT", 50001))

    # Base URL Dapr
    DAPR_BASE_URL: str = f"http://localhost:{DAPR_HTTP_PORT}/v1.0"

    # =====================
    # MongoDB
    # =====================
    MONGODB_URL: str = os.getenv(
        "MONGODB_URL",
        "mongodb://admin:password@mongodb:27017/contentdb?authSource=admin"
    )
    MONGODB_DB: str = os.getenv("MONGODB_DB", "contentdb")

    # =====================
    # File Processing
    # =====================
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".txt", ".docx"}

    # =====================
    # Text Processing
    # =====================
    MICRO_LESSON_DURATION: int = int(os.getenv("MICRO_LESSON_DURATION", 5))  # minutes
    WORDS_PER_MINUTE: int = int(os.getenv("WORDS_PER_MINUTE", 200))

    # =====================
    # Inter-service URLs (via Dapr)
    # =====================
    def get_service_url(self, service_name: str) -> str:
        """
        Retourne l'URL pour appeler un service via Dapr
        """
        return f"{self.DAPR_BASE_URL}/invoke/{service_name}/method"

    @property
    def NOTIFICATION_SERVICE_URL(self) -> str:
        return self.get_service_url("notification-service")

    @property
    def ANALYTICS_SERVICE_URL(self) -> str:
        return self.get_service_url("analytics-service")

    class Config:
        env_file = ".env"


settings = Settings()
