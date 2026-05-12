from fastapi import APIRouter,Depends,HTTPException
from sqlmodel import Session,select
from app.db.engine import get_session
from app.models.models import Balance,Sale
from app.api.deps import get_current_admin

router = APIRouter(tags=["Financial Status"])

@router.get("/financial-summary")
def get_financial_summary(db: Session = Depends(get_session)):
    balance = db.get(Balance, 1)
    if not balance:
        return {"balance_on_hand": 0, "receivables": 0, "actual_balance": 0}
        
    return {
        "balance_on_hand": balance.balance_on_hand,
        "receivables": balance.receivables,
        "actual_balance": balance.balance_on_hand + balance.receivables
    }

@router.patch("/update_balance",dependencies=[Depends(get_current_admin)])
def update_balance(
    db:Session=Depends(get_session),
    balance :float = None
):
    if balance is None:
        raise HTTPException(status_code=400, detail="balance is required")

    db_balance = db.get(Balance,1)
    if not db_balance:
        db_balance = Balance(id=1, balance_on_hand=0.0, receivables=0.0)

    db_balance.balance_on_hand = balance
    db.add(db_balance)
    db.commit()
    db.refresh(db_balance)
    balance_on_hand = db_balance.balance_on_hand
    receivables = db_balance.receivables
    return {
        "balance_on_hand":balance_on_hand,
        "receivables" : receivables,
        "actual_balance": balance_on_hand + receivables
    }

from sqlalchemy import func

@router.post("/balance/recalculate-receivables", dependencies=[Depends(get_current_admin)])
def recalculate_receivables(db: Session = Depends(get_session)):
    # 1. Calculate the 'True' sum from the Sales table
    true_receivables = db.exec(
        select(func.sum(Sale.total_price))
        .where(Sale.payment_status == "pending")
    ).first() or 0.0

    # 2. Update the Balance bucket
    balance = db.get(Balance, 1)
    if not balance:
        balance = Balance(id=1, balance_on_hand=0.0, receivables=true_receivables)
    else:
        balance.receivables = true_receivables
    
    db.add(balance)
    db.commit()
    return {"message": "Receivables synchronized", "receivables": true_receivables}
