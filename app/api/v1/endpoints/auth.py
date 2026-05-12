from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from app.db.engine import get_session
from app.models.models import User,RefreshToken
from app.core import security
from app.core.config import settings
from datetime import timedelta, datetime
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class UserCreate(BaseModel):
    username : str
    password : str

@router.post("/register")
def register(userData: UserCreate, db: Session = Depends(get_session)):
    # Check if user already exists
    username = userData.username
    password = userData.password
    existing_user = db.exec(select(User).where(User.username == username)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    # Create new user
    hashed_password = security.get_password_hash(password)
    new_user = User(username=username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"id": new_user.id, "username": new_user.username}
# Registration endpoint is currently disabled to prevent unauthorized account creation. Admin can create users directly in the database for now.


@router.post("/login")
def login(db: Session = Depends(get_session), form_data: OAuth2PasswordRequestForm = Depends()):
    # 1. Authenticate User
    user = db.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # 2. Create Tokens
    access_token = security.create_token(
        user.id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access"
    )
    refresh_token_str = security.create_token(
        user.id, timedelta(days=30), "refresh"
    )

    # 3. Store Refresh Token for Rotation/Revocation
    db_refresh = RefreshToken(
        token=refresh_token_str, 
        user_id=user.id, 
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(db_refresh)
    db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token_str, "token_type": "bearer"}

@router.post("/refresh")
def refresh_token(token: str, db: Session = Depends(get_session)):
    # 1. Check if token exists and isn't revoked
    db_token = db.exec(select(RefreshToken).where(RefreshToken.token == token)).first()
    if not db_token or db_token.revoked or db_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # 2. ROTATION: Revoke the old token immediately
    db_token.revoked = True
    db.add(db_token)
    
    # 3. Issue new pair
    new_access = security.create_token(db_token.user_id, timedelta(minutes=15), "access")
    new_refresh_str = security.create_token(db_token.user_id, timedelta(days=7), "refresh")
    
    new_db_refresh = RefreshToken(
        token=new_refresh_str, 
        user_id=db_token.user_id, 
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    db.add(new_db_refresh)
    db.commit()

    return {"access_token": new_access, "refresh_token": new_refresh_str}

@router.post("/logout")
def logout(token: str, db: Session = Depends(get_session)):
    db_token = db.exec(select(RefreshToken).where(RefreshToken.token == token)).first()
    if db_token:
        db_token.revoked = True
        db.commit()
    return {"detail": "Successfully logged out"}