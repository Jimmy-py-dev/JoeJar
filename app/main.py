from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from app.db.engine import engine
from app.api.v1.endpoints import auth, products,sales, admin,financial
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Deleted-Sales-Count"],
)

# Create tables on startup (For development only; use Alembic for production)
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

# Include Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(products.router, prefix=f"{settings.API_V1_STR}/products", tags=["Products"])
app.include_router(sales.router, prefix=f"{settings.API_V1_STR}/sales", tags=["Sales"])
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["Admin"])
app.include_router(financial.router,prefix=f"{settings.API_V1_STR}/admin")

@app.get("/")
def root():
    return {"message": "Welcome to the Inventory Management API"}
