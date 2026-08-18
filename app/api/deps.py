"""Dependencies for API endpoints"""
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.database import SessionLocal
from services.auth_service import AuthService
from __models.auth import User


# HTTP Bearer security scheme
security = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    
    auth_service = AuthService(db)
    try:
        payload = auth_service.verify_access_token(token)
        user_id = payload.get('userId')
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Неверный токен авторизации'
            )
        
        # Get user from database
        from __crud.user_repository import UserRepository
        user_repo = UserRepository(db)
        user = user_repo.find_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Пользователь не найден'
            )
        
        return user
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active (verified) user"""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Email не подтвержден'
        )
    return current_user
