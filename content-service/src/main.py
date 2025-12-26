 
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

from .config import settings
from .database import sync_client, async_client
from .routers import courses, lessons, quizzes

# Setup logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Content Service...")
    logger.info(f"MongoDB URL: {settings.mongodb_url}")
    
    # Create upload directory if it doesn't exist
    os.makedirs(settings.upload_dir, exist_ok=True)
    logger.info(f"Upload directory: {settings.upload_dir}")
    
    # Test database connection
    try:
        await async_client.admin.command('ping')
        logger.info("MongoDB connection successful")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Content Service...")
    sync_client.close()
    await async_client.close()

# Create FastAPI app
app = FastAPI(
    title="Content Service - Micro Learning System",
    description="Content management and transformation service",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(courses.router)
app.include_router(lessons.router)
app.include_router(quizzes.router)

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        await async_client.admin.command('ping')
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "service": "content-service",
        "version": "1.0.0",
        "database": db_status
    }

@app.get("/")
async def root():
    return {
        "message": "Content Service - Micro Learning System",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.debug
    )