 
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
import json

from ..models.user import User
from ..models.schemas import UserCreate, UserUpdate
from .auth_service import AuthService

class UserService:
    @staticmethod
    def get_user(db: Session, user_id: int) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User:
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> User:
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        # Check if user exists
        if UserService.get_user_by_email(db, user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        if UserService.get_user_by_username(db, user_data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Create user
        hashed_password = AuthService.get_password_hash(user_data.password)
        db_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role
        )
        
        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not create user"
            )
    
    @staticmethod
    def update_user(db: Session, user_id: int, user_data: UserUpdate) -> User:
        user = UserService.get_user(db, user_id)
        
        update_data = user_data.dict(exclude_unset=True)
        
        # Handle preferences separately
        if 'preferences' in update_data:
            update_data['preferences'] = json.dumps(update_data['preferences'])
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        try:
            db.commit()
            db.refresh(user)
            return user
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not update user"
            )
    
    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        user = UserService.get_user(db, user_id)
        db.delete(user)
        db.commit()
        return True