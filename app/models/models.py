from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel

# --- 1. User & Auth ---
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    role: UserRole = Field(default=UserRole.ADMIN)
    
    # Relationships
    sales: List["Sale"] = Relationship(back_populates="seller")
    logs: List["AuditLog"] = Relationship(back_populates="user")
    RefreshTokens: List["RefreshToken"] = Relationship(back_populates="user")

class RefreshToken(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True) # The actual JWT refresh string
    user_id: int = Field(foreign_key="user.id")
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(days=30)) # 30 days validity
    revoked: bool = Field(default=False) # Used for logout or theft detection
    user: User = Relationship() # Link back to user for easy queries

# --- 2. Product Management ---
class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sku: Optional[str] = Field(default=None, index=True, unique=True) # Optional SKU
    name: str = Field(index=True)
    price: float
    stock_quantity: int = Field(default=0)
    
    # Relationship to track items in sales
    sale_items: List["SaleItem"] = Relationship(back_populates="product")

# --- 3. Buyer (CRM) ---
class Buyer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: Optional[str] = Field(index=True,nullable=True)
    phone: Optional[str] = Field(unique=True)
    address: Optional[str] = None
    
    # Link back to sales
    sales: List["Sale"] = Relationship(back_populates="buyer")

# --- 4. Sales & Transactions ---
class DiscountType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    NONE = "none"

class Sale(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Foreign Keys
    user_id: int = Field(foreign_key="user.id")
    buyer_id: Optional[int] = Field(default=None, foreign_key="buyer.id",index=True) # Optional Buyer
    
    # Financials
    subtotal: float
    discount_type: DiscountType = Field(default=DiscountType.NONE)
    discount_value: float = Field(default=0.0)
    total_price: float
    payment_method: str # e.g., "cash", "bank", "credit"
    payment_status: str = Field(default="paid")
    # Relationships
    seller: User = Relationship(back_populates="sales")
    buyer: Optional[Buyer] = Relationship(back_populates="sales")
    items: List["SaleItem"] = Relationship(back_populates="sale")

class SaleItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sale_id: int = Field(foreign_key="sale.id")
    product_id: int = Field(foreign_key="product.id")
    
    quantity: int
    unit_price_at_sale: float  # The actual price negotiated
    master_price_at_sale: float # The price in the system at that time
    
    # Relationships
    sale: "Sale" = Relationship(back_populates="items")
    product : "Product" = Relationship(back_populates="sale_items")

# --- 5. Audit & History ---
class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: int = Field(foreign_key="user.id")
    
    action: str  # e.g., "STOCK_UPDATE", "PRICE_CHANGE", "PURGE"
    description: str # e.g., "Updated SKU 123 from 10 to 20 units"
    
    user: User = Relationship(back_populates="logs")

# --- 6. Finicial Status ---
class Balance(SQLModel,table=True):
    id : int = Field(default=1,primary_key=True)
    balance_on_hand : float = Field(default=0.0)
    receivables : float = Field(default=0.0)



