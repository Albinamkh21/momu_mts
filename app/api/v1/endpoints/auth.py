"""Auth endpoints for user registration, login, password reset, etc."""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from api.deps import get_db
from __schemas.auth import (
    RegisterRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    RefreshTokenRequest,
    TokenResponse
)
from services.auth_service import AuthService


router = APIRouter()


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user
    
    - **email**: User's email address
    - **password**: Password (minimum 6 characters)
    - **confirmPassword**: Password confirmation
    - **name**: User's full name (optional)
    """
    auth_service = AuthService(db)
    try:
        return await auth_service.register(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Login user and return access and refresh tokens
    
    - **email**: User's email address
    - **password**: User's password
    """
    auth_service = AuthService(db)
    
    # Get device info from request headers
    user_agent = request.headers.get('user-agent', '')
    device_info = f"IP: {request.client.host}, User-Agent: {user_agent}"
    
    try:
        return await auth_service.login(data, device_info)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Verify user's email using verification token
    
    - **token**: Email verification token sent to user's email
    """
    auth_service = AuthService(db)
    try:
        return await auth_service.verify_email(data.token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Send password reset email
    
    - **email**: User's email address
    """
    auth_service = AuthService(db)
    try:
        return await auth_service.forgot_password(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset user's password using reset token
    
    - **token**: Password reset token sent to user's email
    - **password**: New password (minimum 6 characters)
    - **confirmPassword**: Password confirmation
    """
    auth_service = AuthService(db)
    try:
        return await auth_service.reset_password(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token
    
    - **refreshToken**: Valid refresh token
    """
    auth_service = AuthService(db)
    try:
        return await auth_service.refresh_tokens(data.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
