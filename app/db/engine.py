from sqlmodel import create_engine, Session
from app.core.config import settings

# echo=True is helpful for debugging; it prints every SQL query to the console
if settings.DATABASE_URL.startswith("sqlite"):
    # For SQLite, we need to add connect_args to allow multiple threads
    engine = create_engine(
        settings.DATABASE_URL, 
        echo=True, 
        connect_args={"check_same_thread": False},
        pool_pre_ping=True  # Checks connection health before using it
    )
else:
    engine = create_engine(
        settings.DATABASE_URL, 
        pool_pre_ping=True  # Checks connection health before using it
    )

def get_session():
    """Dependency for FastAPI endpoints to get a DB session."""
    with Session(engine) as session:
        yield session