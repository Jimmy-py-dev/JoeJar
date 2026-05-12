#All depedencies from fastapi import Depends
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlmodel import Session
from app.db.engine import get_session
from app.models.models import User,UserRole
from app.core.config import settings

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_current_user(db: Session = Depends(get_session), token: str = Depends(reusable_oauth2)) -> User:
    try:
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]) or None
        
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(status_code=403, detail="Could not validate credentials")
            
    except JWTError:
        print("JWTError") # Debugging line to check if JWTError is being raised
        raise HTTPException(status_code=403, detail="Could not validate credentials")
        
    
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="The user does not have enough privileges"
        )
    return current_user