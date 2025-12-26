from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import time
import logging

logger = logging.getLogger(__name__)

# Initialize with a default connection, will be configured later
engine = None
SessionLocal = None
Base = None

def init_database(database_url: str):
    """Initialize database connection"""
    global engine, SessionLocal, Base
    
    logger.info(f"Initializing database connection to: {database_url}")
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            engine = create_engine(
                database_url,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=False,  # Set to True for SQL logging
                connect_args={"connect_timeout": 10}
            )
            
            # Test connection
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            Base = declarative_base()
            
            logger.info("✓ Database connection established")
            return True
            
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                logger.error("✗ Max retries reached, could not connect to database")
                return False

def get_db():
    """Dependency for database session"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Import models after Base is defined
from .models.user import User