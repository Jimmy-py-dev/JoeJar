from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from typing import List
from app.db.engine import get_session
from app.models.models import AuditLog, User,Balance
from app.api.deps import get_current_admin
import pandas as pd
from fastapi.responses import StreamingResponse
import io

router = APIRouter()

@router.get("/audit-logs", response_model=List[AuditLog])
def get_audit_logs(
    db: Session = Depends(get_session), 
    admin: User = Depends(get_current_admin)
):
    return db.exec(select(AuditLog).order_by(AuditLog.timestamp.desc())).all()

