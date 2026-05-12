from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "Odoo Lite"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = Field(default="SUPER_SECRET_CHANGE_ME")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 # Short-lived access tokens for better security
    
    # Database
    # Example: postgresql://user:password@localhost:5432/dbname
    DATABASE_URL: str
    
    # Pydantic configuration to read .env file
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()