from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Union

from postgrest import PostgrestClient # type: ignore
from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, validator # type: ignore
from pydantic_settings import BaseSettings, SettingsConfigDict # type: ignore
from supabase import Client, create_client # type: ignore

import logging
import logging.config
from utils.logger import setup_logger

class Environment(str, Enum):
    """Valid environment settings"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class DatabaseConfig(BaseSettings):
    """Database-specific configuration settings"""
    SUPABASE_URL: str
    SUPABASE_KEY: SecretStr
    SUPABASE_PROJECT_ID: str
    
    class Config:
        extra = "allow"  # Allow extra fields
    
    @validator('SUPABASE_URL')
    def validate_supabase_url(cls, v: str) -> str:
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Invalid Supabase URL format")
        return v

class AWSConfig(BaseSettings):
    """AWS-specific configuration settings"""
    AWS_ACCESS_KEY: SecretStr
    AWS_SECRET_KEY: SecretStr
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str

    class Config:
        extra = "allow"  # Allow extra fields

class Settings(BaseSettings):
    """
    Application configuration with validation.
    Handles all environment variables and provides validated settings.
    
    For Demo Setup:
    1. Ensure .env file exists with required keys
    2. Verify OpenAI API key
    3. Test database connection
    4. Confirm SMTP settings
    """
    # Application Settings
    APP_NAME: str = "Domi AI"
    ENV: Environment = Environment.DEVELOPMENT
    LOG_LEVEL: str = "INFO"
    CONFIG_VERSION: str = "1.0.0"
    
    # Service timeouts and limits
    REQUEST_TIMEOUT: int = Field(default=60, ge=1, le=300)
    MAX_RETRIES: int = Field(default=3, ge=1, le=10)
    
    # Integration Settings
    OPENAI_API_KEY: SecretStr
    MODEL_NAME: str = "gpt-4-1106-preview"
    TEMPERATURE: float = Field(default=0.7, ge=0, le=1)
    
    # Email Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    SMTP_USER: str
    SMTP_PASSWORD: SecretStr
    
    # Security Settings
    JWT_SECRET: SecretStr
    ENCRYPTION_KEY: SecretStr
    
    # Include sub-configurations
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    aws: AWSConfig = Field(default_factory=AWSConfig)
    
    # Internal state
    _supabase_client: Optional[Client] = None
    _last_client_refresh: Optional[datetime] = None
    CLIENT_REFRESH_INTERVAL: timedelta = timedelta(minutes=30)

    @property
    def supabase(self) -> Client:
        """Get configured Supabase client with automatic refresh"""
        now = datetime.utcnow()
        
        # Initialize or refresh client if needed
        if (
            self._supabase_client is None or
            self._last_client_refresh is None or
            now - self._last_client_refresh > self.CLIENT_REFRESH_INTERVAL
        ):
            try:
                self._supabase_client = create_client(
                    self.db.SUPABASE_URL,
                    self.db.SUPABASE_KEY.get_secret_value(),
                    options={
                        'persist_session': False,
                        'auto_refresh_token': True,
                        'timeout': self.REQUEST_TIMEOUT
                    }
                )
                self._last_client_refresh = now
                logging.debug("Supabase client initialized/refreshed successfully")
            except Exception as e:
                logging.error(f"Failed to create Supabase client: {str(e)}")
                raise RuntimeError("Supabase client initialization failed") from e
                
        return self._supabase_client

    @property
    def postgrest(self) -> PostgrestClient:
        """Get configured PostgREST client"""
        return self.supabase.postgrest

    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        case_sensitive = True
        validate_assignment = True
        extra = "allow"

def initialize_app() -> None:
    """Initialize all application components with proper error handling"""
    try:
        settings = get_settings()
        logger = setup_logger("app.config", log_file="logs/app.log")
        
        # Validate critical settings with demo-friendly messages
        if not settings.OPENAI_API_KEY.get_secret_value():
            raise ValueError("OpenAI API key not configured. Add it to .env file")
            
        if len(settings.JWT_SECRET.get_secret_value()) < 32:
            raise ValueError("JWT secret must be at least 32 characters")
            
        logging.info(f"Starting {settings.APP_NAME} in {settings.ENV} environment")
        
    except Exception as e:
        logging.error(f"Application initialization failed: {str(e)}")
        raise RuntimeError("Failed to initialize application") from e

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get cached application settings.
    Uses LRU cache to avoid repeated environment variable reads.
    """
    try:
        settings = Settings()
        logging.info(f"Settings loaded successfully for environment: {settings.ENV}")
        return settings
    except Exception as e:
        logging.error(f"Failed to load settings: {str(e)}")
        raise RuntimeError("Application configuration failed") from e