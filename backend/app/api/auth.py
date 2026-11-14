"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, db_session, get_current_user
from app.models.auth import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.schemas.common import Message
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(db_session)):
    user = auth_service.authenticate(db, payload.username, payload.password, client_ip(request))
    token, expires_in = auth_service.issue_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": auth_service.serialize_user(user),
    }


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(db_session)):
    user = auth_service.register_employee_user(
        db, payload.username, payload.email, payload.password, payload.employee_id
    )
    return auth_service.serialize_user(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return auth_service.serialize_user(user)


@router.post("/change-password", response_model=Message)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
):
    auth_service.change_password(db, user, payload.current_password, payload.new_password)
    return {"message": "Password updated successfully"}
