from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..models.user import User
from ..models.schemas import TokenData

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.access_token_expire_minutes
            )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.secret_key, 
            algorithm=settings.algorithm
        )
        return encoded_jwt
    
    @staticmethod
    def authenticate_user(
        db: Session, 
        username: str, 
        password: str
    ) -> Optional[User]:
        user = db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user:
            return None
        if not AuthService.verify_password(password, user.hashed_password):
            return None
        return user
    
    @staticmethod
    def get_current_user(token: str, db: Session) -> User:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(
                token, 
                settings.secret_key, 
                algorithms=[settings.algorithm]
            )
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except JWTError:
            raise credentials_exception
        
        user = db.query(User).filter(
            (User.username == token_data.username) | 
            (User.email == token_data.username)
        ).first()
        
        if user is None:
            raise credentials_exception
        return user