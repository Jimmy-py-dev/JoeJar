from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
from app.db.engine import get_session
from app.models.models import Product, AuditLog, User
from app.api.deps import get_current_admin, get_current_user

router = APIRouter()

class ProductUpdate(BaseModel):
    price: Optional[float] = None
    stock_quantity: Optional[int] = None

# 1. List all products (Available to both Admin and User for the Shop)
@router.get("/", response_model=List[Product])
def read_products(db: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return db.exec(select(Product)).all()

# 2. Create a new product (Admin Only)
@router.post("/", response_model=Product)
def create_product(
    product: Product, 
    db: Session = Depends(get_session), 
    admin: User = Depends(get_current_admin)
):
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Log the creation
    log = AuditLog(
        user_id=admin.id,
        action="PRODUCT_CREATED",
        description=f"{admin.username} created product {product.name} (SKU: {product.sku}) with price {product.price}"
    )
    db.add(log)
    db.commit()
    return product

# 3. Update Inventory/Price (Admin Only)
@router.patch("/{product_id}", response_model=Product)
def update_product(
    product_id: int, 
    updates: ProductUpdate,
    db: Session = Depends(get_session), 
    admin: User = Depends(get_current_admin)
):
    db_product = db.get(Product, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    old_stock = db_product.stock_quantity
    old_price = db_product.price

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        return db_product  # No changes

    for key, value in update_data.items():
        setattr(db_product, key, value)
    
    db.add(db_product)
    
    # Generate Audit Description
    changes = []
    if updates.stock_quantity is not None:
        changes.append(f"Stock: {old_stock} -> {db_product.stock_quantity}")
    if updates.price is not None:
        changes.append(f"Price: {old_price} -> {db_product.price}")
    
    # Log the changes
    if changes:
        log = AuditLog(
            user_id=admin.id,
            action="INVENTORY_UPDATE",
            description=f"Updated {db_product.name}: " + ", ".join(changes)
        )
        db.add(log)

    db.commit()
    db.refresh(db_product)
    return db_product