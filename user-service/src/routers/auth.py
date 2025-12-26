from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.schemas import Token, LoginRequest, RegisterRequest, UserResponse
from ..services.auth_service import AuthService
from ..services.user_service import UserService
from ..models.schemas import UserCreate

router = APIRouter(prefix="/auth", tags=["authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """Register a new user"""
    print(f"Register request received for username: {user_data.username}")
    
    user_create = UserCreate(
        email=user_data.email if user_data.email else f"{user_data.username}@example.com",
        username=user_data.username,
        password=user_data.password,
        full_name=user_data.full_name
    )
    
    return UserService.create_user(db, user_create)

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login user and return JWT token"""
    print(f"Login attempt for username: {form_data.username}")
    
    user = AuthService.authenticate_user(
        db, form_data.username, form_data.password
    )
    
    if not user:
        print(f"Authentication failed for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = AuthService.create_access_token(
        data={"sub": user.username}
    )
    
    print(f"Login successful for user: {user.username}")
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Get current user information"""
    user = AuthService.get_current_user(token, db)
    return user