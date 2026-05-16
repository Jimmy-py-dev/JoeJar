from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import List, Optional
from app.db.engine import get_session
from app.models.models import Sale, SaleItem, Product, AuditLog, User, DiscountType,UserRole,Buyer,Balance
from app.api.deps import get_current_user,get_current_admin
from typing import Optional
from datetime import datetime,timezone
import io
import pandas as pd

from pydantic import BaseModel
class SaleItemCreate(BaseModel):
    product_id: int
    quantity: int
    price: float # Price sent from Frontend, can be overridden

class SaleCreate(BaseModel):
    buyer_name: Optional[str] = None #Only for non-existing buyer 
    buyer_id : Optional[int] = None
    items: List[SaleItemCreate]
    discount_type: DiscountType = DiscountType.NONE
    discount_value: float = 0.0
    payment_method: str

router = APIRouter()

class BuyerRead(BaseModel):
    id: int
    name: str

@router.get("/buyers", response_model=List[BuyerRead])
def read_buyers(db: Session = Depends(get_session),
               user : User = Depends(get_current_user)):
    return db.exec(select(Buyer.id, Buyer.name)).all()

@router.post("/confirm", response_model=Sale)
def confirm_sale(
    sale_in: SaleCreate, # Now SaleItemCreate needs to include 'price'
    db: Session = Depends(get_session), 
    user: User = Depends(get_current_user)
):  
    b_id = sale_in.buyer_id
    b__name = sale_in.buyer_name.strip() if sale_in.buyer_name else None

    if b_id:
        buyer = db.get(Buyer, b_id)
        if not buyer:
            raise HTTPException(status_code=404, detail="Buyer not found")
    elif b__name and b__name.lower() != "guest":
        new_buyer = Buyer(
            name = b__name
        )
        db.add(new_buyer)
        db.flush()
        b_id = new_buyer.id
        
    new_sale = Sale(
        user_id=user.id,
        buyer_id=b_id,
        subtotal=0, # Calculated below
        discount_type=sale_in.discount_type,
        discount_value=sale_in.discount_value,
        total_price=0 ,
        payment_method=sale_in.payment_method,
        payment_status="pending" if sale_in.payment_method == "credit" else "paid"
    )
    db.add(new_sale)
    db.flush() 

    running_subtotal = 0.0

    for item_in in sale_in.items:
        product = db.get(Product, item_in.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # 1. Record the sale item with the price sent from Frontend
        sale_item = SaleItem(
            sale_id=new_sale.id,
            product_id=product.id,
            quantity=item_in.quantity,
            unit_price_at_sale=item_in.price, # Frontend's price
            master_price_at_sale=product.price # System's price
        )
        db.add(sale_item)

        # 2. Check for Price Override for the Audit Log
        if item_in.price != product.price:
            log = AuditLog(
                user_id=user.id,
                action="PRICE_OVERRIDE",
                description=(
                    f"User {user.username} sold {product.name} at ${item_in.price} "
                    f"(System Price: ${product.price})"
                )
            )
            db.add(log)

        # 3. Decrement Stock
        product.stock_quantity -= item_in.quantity
        running_subtotal += (item_in.price * item_in.quantity)
        db.add(product)

    # 4. Finalize Sale Totals
    new_sale.subtotal = running_subtotal
    # Apply global discount if any
    if new_sale.discount_type == DiscountType.PERCENTAGE:
        discount = running_subtotal * (new_sale.discount_value / 100)
    else:
        discount = new_sale.discount_value
    
    new_sale.total_price = max(0, running_subtotal - discount)
    
    db.add(new_sale)

    # Add to Balance
    balance = db.get(Balance, 1)
    if not balance:
        balance = Balance(id=1, balance_on_hand=0.0, receivables=0.0)
        db.add(balance)

    if new_sale.payment_status == "paid":
        balance.balance_on_hand += new_sale.total_price
    else:
        balance.receivables += new_sale.total_price
    db.add(balance)

    db.commit()
    db.refresh(new_sale)
    return new_sale

class SaleItemRes(BaseModel):
    item: str
    quantity: int
    price: float # Changed to float for accurate currency display

class SaleHistory(BaseModel):
    id: int               # Added so frontend can show Order #
    timestamp: datetime   # Added so frontend can show the date
    buyer_name: Optional[str] = None
    items: List[SaleItemRes]
    discount: float       # Changed to float 
    total: float
    payment_method: str
    payment_status: str
    seller: str

def get_sales_for_history(db: Session, method: Optional[str] = None):
    if method and method not in ["cash", "bank", "credit"]:
        raise HTTPException(status_code=400, detail="Invalid payment method filter")
    if not method:
        return db.exec(select(Sale).order_by(Sale.timestamp.desc())).all()
    return db.exec(
        select(Sale)
        .where((Sale.payment_method == method) & (Sale.payment_status == "pending"))
        .order_by(Sale.timestamp.desc())
    ).all()

def build_sale_history(db: Session, sales_db: List[Sale]):
    history = []

    for sale in sales_db:
        seller = db.get(User, sale.user_id)
        seller_name = seller.username if seller else "System"

        buyer_name = None
        if sale.buyer_id:
            buyer = db.get(Buyer, sale.buyer_id)
            buyer_name = buyer.name if buyer else None

        raw_items = db.exec(select(SaleItem).where(SaleItem.sale_id == sale.id)).all()
        items_list = []
        for si in raw_items:
            prod = db.get(Product, si.product_id)
            items_list.append(SaleItemRes(
                item=prod.name if prod else "Deleted Product",
                quantity=si.quantity,
                price=float(si.unit_price_at_sale)
            ))

        history.append(SaleHistory(
            id=sale.id,
            timestamp=sale.timestamp,
            buyer_name=buyer_name,
            items=items_list,
            discount=float(sale.discount_value),
            total=float(sale.total_price),
            payment_method=sale.payment_method,
            payment_status=sale.payment_status,
            seller=seller_name
        ))

    return history

def purge_sales_before_current_month(db: Session, current_admin: User):
    cutoff = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    old_sales = db.exec(select(Sale).where(Sale.timestamp < cutoff)).all()
    deleted_count = 0

    for sale in old_sales:
        sale_items = db.exec(select(SaleItem).where(SaleItem.sale_id == sale.id)).all()
        for item in sale_items:
            db.delete(item)
        db.delete(sale)
        deleted_count += 1

    if deleted_count:
        audit_log = AuditLog(
            user_id=current_admin.id,
            action="SALES_PURGE",
            description=f"Export cleanup deleted {deleted_count} sales before {cutoff.date()}"
        )
        db.add(audit_log)

        balance = db.get(Balance, 1)
        if balance:
            pending_receivables = sum(
                sale.total_price for sale in db.exec(
                    select(Sale).where(Sale.payment_status == "pending")
                ).all()
            )
            balance.receivables = pending_receivables
            db.add(balance)

    db.commit()
    return deleted_count

# --- Completed Endpoint ---
@router.get("/", response_model=List[SaleHistory])
def read_sales(
    method: Optional[str] = None, #just for credit sales filtering, can be "cash", "bank", "credit"
    db: Session = Depends(get_session), 
    current_admin: User = Depends(get_current_admin)
):
    return build_sale_history(db, get_sales_for_history(db, method))

@router.get("/export")
def export_sales(
    method: Optional[str] = None,
    purge_previous_months: bool = False,
    db: Session = Depends(get_session),
    current_admin: User = Depends(get_current_admin)
):
    sales = get_sales_for_history(db, method)
    history = build_sale_history(db, sales)
    rows = []

    for sale in history:
        buyer_name = sale.buyer_name or "Guest"
        if not sale.items:
            rows.append({
                "Order ID": sale.id,
                "Timestamp": sale.timestamp,
                "Buyer": buyer_name,
                "Cashier": sale.seller,
                "Payment Method": sale.payment_method,
                "Payment Status": sale.payment_status,
                "Item": "",
                "Quantity": 0,
                "Unit Price": 0.0,
                "Line Total": 0.0,
                "Discount": sale.discount,
                "Sale Total": sale.total,
            })
            continue

        for item in sale.items:
            rows.append({
                "Order ID": sale.id,
                "Timestamp": sale.timestamp,
                "Buyer": buyer_name,
                "Payment Method": sale.payment_method,
                "Payment Status": sale.payment_status,
                "Item": item.item,
                "Quantity": item.quantity,
                "Unit Price": item.price,
                "Total": item.price * item.quantity,
                "Discount": sale.discount,
            })

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sales History")
    output.seek(0)

    deleted_count = 0
    if purge_previous_months:
        deleted_count = purge_sales_before_current_month(db, current_admin)

    suffix = method or "all"
    filename = f"sales-history-{suffix}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.xlsx"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Deleted-Sales-Count": str(deleted_count)
    }
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

@router.patch("/{sale_id}/confirm_payment")
def confirm_payment(
    sale_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    sale = db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    if sale.payment_status != "pending":
        raise HTTPException(status_code=400, detail="Payment already confirmed or not pending")
    sale.payment_status = "paid"
    db.add(sale)
    db.flush()
    db.refresh(sale)

    audit_log = AuditLog(
        user_id=current_user.id,
        action="PAYMENT_CONFIRMED",
        description=f"{current_user.username} confirmed payment for Sale ID {sale_id}"
    )
    db.add(audit_log)

    balance = db.get(Balance, 1)
    if balance:
        balance.receivables -= sale.total_price
        balance.balance_on_hand += sale.total_price
        db.add(balance)
    
    db.commit()
    return {"detail": "Payment confirmed successfully"}
