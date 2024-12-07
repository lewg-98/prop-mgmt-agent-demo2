# Standard library imports
import os
import logging
import logging.config
from typing import Optional, Dict, Any
from pathlib import Path
from functools import lru_cache

# Third-party imports
from pydantic_settings import BaseSettings
from pydantic import SecretStr, validator
from postgrest import PostgrestClient
from supabase import create_client, Client

class Settings(BaseSettings):
    """
    Application configuration with validation.
    Handles all environment variables and provides validated settings for the application.
    """
    
    # Application Settings
    APP_NAME: str = "Domi AI"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    REQUEST_TIMEOUT: int = 60
    MAX_RETRIES: int = 3
    
    # Supabase Settings
    SUPABASE_URL: str
    SUPABASE_KEY: SecretStr
    SUPABASE_PROJECT_ID: str
    
    # OpenAI Settings
    OPENAI_API_KEY: SecretStr
    MODEL_NAME: str = "gpt-4o-mini"
    TEMPERATURE: float = 0.7
    
    # AWS Settings
    AWS_ACCESS_KEY: SecretStr
    AWS_SECRET_KEY: SecretStr
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str

    # Email Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str
    SMTP_PASSWORD: SecretStr

    # Security Settings
    JWT_SECRET: SecretStr
    ENCRYPTION_KEY: SecretStr
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        case_sensitive = True
        
    # Validators
    @validator("TEMPERATURE")
    def validate_temperature(cls, v: float) -> float:
        """Ensure temperature is within valid range"""
        if not 0 <= v <= 1:
            raise ValueError("Temperature must be between 0 and 1")
        return v

    @validator("SMTP_PORT")
    def validate_smtp_port(cls, v: int) -> int:
        """Ensure SMTP port is valid"""
        if not 0 <= v <= 65535:
            raise ValueError("SMTP port must be between 0 and 65535")
        return v
    
    # Client Properties
    @property
    def supabase(self) -> Client:
        """Get configured Supabase client"""
        try:
            return create_client(
                self.SUPABASE_URL,
                self.SUPABASE_KEY.get_secret_value()
            )
        except Exception as e:
            logging.error(f"Failed to create Supabase client: {str(e)}")
            raise RuntimeError("Supabase client initialization failed") from e

    @property
    def postgrest(self) -> PostgrestClient:
        """Get configured PostgREST client"""
        return self.supabase.postgrest

def setup_logging(settings: Settings) -> None:
    """
    Configure application logging with both console and file handlers.
    Creates a rotating log file with size limits.
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
            },
            "simple": {
                "format": "%(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "level": settings.LOG_LEVEL
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_dir / "app.log",
                "maxBytes": 1024 * 1024,  # 1MB
                "backupCount": 5,
                "formatter": "detailed",
                "level": settings.LOG_LEVEL
            }
        },
        "root": {
            "level": settings.LOG_LEVEL,
            "handlers": ["console", "file"]
        }
    }
    
    try:
        logging.config.dictConfig(log_config)
        logging.info("Logging configured successfully")
    except Exception as e:
        print(f"Failed to configure logging: {str(e)}")
        raise

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.
    Uses LRU cache to avoid reading environment variables repeatedly.
    """
    try:
        return Settings()
    except Exception as e:
        logging.error(f"Failed to load settings: {str(e)}")
        raise RuntimeError("Application configuration failed") from e

def initialize_app() -> None:
    """
    Initialize all application components.
    Validates critical settings and sets up logging.
    """
    try:
        settings = get_settings()
        setup_logging(settings)
        
        # Validate critical settings
        critical_settings = [
            ("Supabase URL", settings.SUPABASE_URL),
            ("Supabase Key", settings.SUPABASE_KEY.get_secret_value()),
            ("OpenAI API Key", settings.OPENAI_API_KEY.get_secret_value()),
            ("AWS Access Key", settings.AWS_ACCESS_KEY.get_secret_value()),
            ("SMTP Password", settings.SMTP_PASSWORD.get_secret_value()),
            ("JWT Secret", settings.JWT_SECRET.get_secret_value()),
            ("Encryption Key", settings.ENCRYPTION_KEY.get_secret_value())
        ]
        
        for name, value in critical_settings:
            if not value:
                raise ValueError(f"{name} not configured")
        
        logging.info(f"Starting {settings.APP_NAME} in {settings.ENV} environment")
        logging.debug("All critical settings validated successfully")
        
    except Exception as e:
        logging.error(f"Application initialization failed: {str(e)}")
        raise RuntimeError("Failed to initialize application") from e