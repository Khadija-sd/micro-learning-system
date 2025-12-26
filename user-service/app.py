from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import hashlib
import time
import uvicorn
import base64
import json
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(
    title="User Service - Micro Learning System",
    description="User authentication and management service",
    version="1.0.0"
)

# ========== CONFIGURATION ==========
DATABASE_URL = "postgresql://user:password@postgres:5432/userdb"

def get_db_connection():
    """Get PostgreSQL connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)  # CORRECTION ICI
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# ========== INITIALISATION BASE DE DONNÉES ==========
def init_database():
    """Initialize database tables"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            # Create users table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    full_name VARCHAR(100),
                    hashed_password VARCHAR(255) NOT NULL,
                    role VARCHAR(20) DEFAULT 'student',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at VARCHAR(50)
                )
            """)
            conn.commit()
            print("✓ Database table 'users' created/verified")
            return True
    except Exception as e:
        print(f"✗ Database initialization error: {e}")
        return False
    finally:
        conn.close()

# Initialize on startup
print("=" * 50)
print("INITIALIZING USER SERVICE")
print("=" * 50)
print("Initializing database...")
if init_database():
    print("✓ Database initialized successfully")
else:
    print("✗ Database initialization failed")
print("=" * 50)

# ========== MODÈLES ==========
class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "student"

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: str = "student"
    is_active: bool = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ========== FONCTIONS UTILITAIRES ==========
def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(username: str) -> str:
    """Create JWT-like token (base64 encoded)"""
    token_data = {
        "username": username,
        "expires": time.time() + 86400  # 24 hours
    }
    token_json = json.dumps(token_data)
    return base64.b64encode(token_json.encode()).decode()

def verify_token(token: str) -> Optional[str]:
    """Verify and decode token"""
    try:
        # Add padding if needed for base64
        missing_padding = len(token) % 4
        if missing_padding:
            token += '=' * (4 - missing_padding)
        
        # Decode token
        token_json = base64.b64decode(token).decode('utf-8')
        token_data = json.loads(token_json)
        
        # Check expiration
        if token_data.get("expires", 0) > time.time():
            return token_data.get("username")
    except Exception as e:
        print(f"[TOKEN ERROR] {e}")
    return None

# ========== ENDPOINTS ==========
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "User Service - Micro Learning System",
        "version": "1.0.0",
        "database": "PostgreSQL",
        "endpoints": {
            "GET /health": "Health check with database status",
            "POST /register": "Register new user",
            "POST /login": "Login and get access token",
            "GET /me": "Get current user info (requires Authorization: Bearer <token>)"
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint with database connection test"""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            db_status = "connected"
            conn.close()
        except:
            db_status = "error"
    else:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "service": "user-service",
        "database": db_status,
        "timestamp": time.time()
    }

@app.post("/register", response_model=UserResponse)
async def register(user: UserRegister):
    """
    Register a new user
    
    Example JSON:
    {
        "username": "john_doe",
        "password": "secure123",
        "email": "john@example.com",
        "full_name": "John Doe",
        "role": "student"
    }
    """
    print(f"[REGISTER] Attempt for username: {user.username}")
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Set default values
            email = user.email or f"{user.username}@example.com"
            full_name = user.full_name or user.username
            
            # Check if user already exists
            cur.execute(
                "SELECT id FROM users WHERE username = %s OR email = %s",
                (user.username, email)
            )
            existing = cur.fetchone()
            
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail="Username or email already registered"
                )
            
            # Insert new user
            cur.execute("""
                INSERT INTO users 
                (username, email, full_name, hashed_password, role, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, username, email, full_name, role, is_active
            """, (
                user.username,
                email,
                full_name,
                hash_password(user.password),
                user.role,
                True,  # is_active
                str(time.time())  # created_at
            ))
            
            # Get the created user
            new_user = cur.fetchone()
            conn.commit()
            
            print(f"[REGISTER] Success: {user.username} (ID: {new_user['id']})")
            
            # Ensure is_active is boolean
            if new_user['is_active'] is None:
                new_user['is_active'] = True
            
            return UserResponse(**new_user)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[REGISTER ERROR] {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Registration failed: {str(e)}"
        )
    finally:
        conn.close()

@app.post("/login", response_model=TokenResponse)
async def login(user: UserLogin):
    """
    Login user and return access token
    
    Example JSON:
    {
        "username": "john_doe",
        "password": "secure123"
    }
    """
    print(f"[LOGIN] Attempt for username: {user.username}")
    
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Find user by username
            cur.execute(
                "SELECT * FROM users WHERE username = %s",
                (user.username,)
            )
            db_user = cur.fetchone()
            
            if not db_user:
                print(f"[LOGIN] User not found: {user.username}")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid username or password"
                )
            
            # Verify password
            if hash_password(user.password) != db_user['hashed_password']:
                print(f"[LOGIN] Invalid password for: {user.username}")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid username or password"
                )
            
            # Check if user is active
            if not db_user['is_active']:
                raise HTTPException(
                    status_code=403,
                    detail="Account is deactivated"
                )
            
            # Create and return token
            token = create_token(user.username)
            
            print(f"[LOGIN] Success: {user.username}")
            return {
                "access_token": token,
                "token_type": "bearer"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGIN ERROR] {e}")
        raise HTTPException(
            status_code=500,
            detail="Login failed"
        )
    finally:
        conn.close()

@app.get("/me", response_model=UserResponse)
async def get_current_user(authorization: Optional[str] = None):
    """
    Get current authenticated user information
    
    Requires: Authorization: Bearer <token>
    """
    print(f"[ME] Request received")
    
    # Check authorization header
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must start with 'Bearer '"
        )
    
    # Extract and verify token
    token = authorization[7:]
    username = verify_token(token)
    
    if not username:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get user from database
            cur.execute("""
                SELECT id, username, email, full_name, role, is_active 
                FROM users 
                WHERE username = %s
            """, (username,))
            
            user = cur.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=404,
                    detail="User not found"
                )
            
            print(f"[ME] Success: {username}")
            
            # Ensure is_active is boolean
            if user['is_active'] is None:
                user['is_active'] = True
            
            return UserResponse(**user)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ME ERROR] {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get user information"
        )
    finally:
        conn.close()

# ========== EXÉCUTION ==========
if __name__ == "__main__":
    print("=" * 50)
    print("USER SERVICE STARTED")
    print("=" * 50)
    print(f"Database: {DATABASE_URL}")
    print("Port: 8000")
    print("Endpoints:")
    print("  GET  /         - API information")
    print("  GET  /health   - Health check")
    print("  POST /register - Register new user")
    print("  POST /login    - Login user")
    print("  GET  /me       - Get current user (requires token)")
    print("=" * 50)
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_level="info",
        access_log=True
    )