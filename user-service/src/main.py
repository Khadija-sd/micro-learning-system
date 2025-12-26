from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict
import hashlib
import jwt
from datetime import datetime, timedelta
import uvicorn

app = FastAPI(
    title="User Service - Micro Learning System",
    description="User authentication and management service",
    version="1.0.0"
)

# ========== MODÈLES ==========
class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "student"

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool = True

# ========== BASE DE DONNÉES SIMULÉE ==========
fake_users_db: Dict[str, Dict] = {}

# ========== CONFIGURATION ==========
SECRET_KEY = "development-secret-key-change-in-production"
ALGORITHM = "HS256"

# ========== FONCTIONS D'AIDE ==========
def get_password_hash(password: str) -> str:
    """Hacher le mot de passe"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_access_token(data: dict) -> str:
    """Créer un token JWT"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ========== ENDPOINTS ==========
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "user-service",
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    return {
        "message": "User Service - Micro Learning System",
        "endpoints": {
            "POST /auth/register": "Register new user",
            "POST /auth/login": "Login user",
            "GET /auth/me": "Get current user"
        }
    }

@app.post("/auth/register")
async def register(user_data: RegisterRequest):
    """Register a new user"""
    print(f"Register: {user_data.username}")
    
    if user_data.username in fake_users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Créer un nouvel utilisateur
    user_id = len(fake_users_db) + 1
    new_user = {
        "id": user_id,
        "username": user_data.username,
        "email": user_data.email or f"{user_data.username}@example.com",
        "full_name": user_data.full_name,
        "hashed_password": get_password_hash(user_data.password),
        "role": user_data.role,
        "is_active": True
    }
    
    fake_users_db[user_data.username] = new_user
    
    return UserResponse(**new_user)

@app.post("/auth/login")
async def login(user_data: LoginRequest):
    """Login user and return JWT token"""
    print(f"Login attempt: {user_data.username}")
    
    user = fake_users_db.get(user_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Vérifier le mot de passe
    hashed_input = get_password_hash(user_data.password)
    if hashed_input != user["hashed_password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Créer le token
    access_token = create_access_token({"sub": user["username"]})
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me")
async def get_current_user(authorization: Optional[str] = None):
    """Get current user information"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token"
        )
    
    token = authorization[7:]
    
    try:
        # Décoder le token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        
        if not username or username not in fake_users_db:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        user = fake_users_db[username]
        return UserResponse(**user)
        
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)