from typing import Tuple, Dict, Optional, List
import re
import bleach
from datetime import datetime, timedelta
import logging
from pydantic import BaseModel, EmailStr, Field, validator
from enum import Enum

# Configure logger
logger = logging.getLogger(__name__)

class ContactMethod(Enum):
    """Valid contact method preferences"""
    EMAIL = "email"
    PHONE = "phone"
    BOTH = "both"

class MaintenanceRequestData(BaseModel):
    """
    Pydantic model for maintenance request validation for demo environment.
    Provides automatic validation and data cleaning.
    """
    property_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=10, max_length=1000)
    email: EmailStr
    phone: str = Field(..., pattern=r'^\+?1?\d{9,15}$')
    preferred_contact: ContactMethod = Field(default=ContactMethod.EMAIL)
    photo_urls: Optional[List[str]] = Field(default=None, max_items=5)
    urgent: bool = Field(default=False)

    @validator('phone')
    def format_phone(cls, v: str) -> str:
        """Format phone numbers consistently"""
        # Remove all non-numeric characters
        numbers_only = re.sub(r'\D', '', v)
        if len(numbers_only) == 10:
            return f"+1{numbers_only}"
        elif len(numbers_only) > 10:
            return f"+{numbers_only}"
        raise ValueError("Invalid phone number format")

    @validator('description')
    def clean_description(cls, v: str) -> str:
        """Clean and validate description text"""
        cleaned = bleach.clean(v, strip=True)
        if len(cleaned.strip()) < 10:
            raise ValueError("Description must be at least 10 characters")
        return cleaned

class RequestValidator:
    """
    Validates and sanitizes maintenance request inputs.
    Includes rate limiting and input validation.
    """
    
    def __init__(self, 
                 max_requests: int = 10,
                 time_window: int = 60,
                 max_description_length: int = 1000):
        """
        Initialize validator with configurable limits for demo environment.
        
        Args:
            max_requests: Maximum requests per time window
            time_window: Time window in seconds
            max_description_length: Maximum description length
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.max_description_length = max_description_length
        self._setup_rate_limits()
        logger.info("Request validator initialized")

    def _setup_rate_limits(self) -> None:
        """Initialize rate limiting tracker"""
        self.request_times: List[datetime] = []

    def sanitize_input(self, text: str) -> str:
        """
        Sanitize user input to prevent XSS attacks.
        
        Args:
            text: Raw input text
            
        Returns:
            Cleaned text string
        """
        try:
            return bleach.clean(text, strip=True)
        except Exception as e:
            logger.error(f"Input sanitization failed: {str(e)}")
            raise ValueError("Invalid input text") from e

    def check_rate_limit(self, client_id: Optional[str] = None) -> bool:
        """
        Check if request is within rate limits for demo environment.
        
        Args:
            client_id: Optional client identifier for per-client limiting
            
        Returns:
            Boolean indicating if request is allowed
        """
        try:
            now = datetime.now()
            
            # Clean old requests
            self.request_times = [
                t for t in self.request_times
                if now - t < timedelta(seconds=self.time_window)
            ]
            
            # Check limit
            if len(self.request_times) >= self.max_requests:
                logger.warning(f"Rate limit exceeded: {len(self.request_times)} requests")
                return False
                
            self.request_times.append(now)
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            return False

    def validate_request(self, data: Dict) -> Tuple[bool, str]:
        """
        Validate complete maintenance request for demo environment.
        
        Args:
            data: Request data dictionary
            
        Returns:
            Tuple of (is_valid, error_message)
            
        Example:
            >>> validator = RequestValidator()
            >>> is_valid, error = validator.validate_request({
            ...     "property_id": "123",
            ...     "description": "Leaking faucet in kitchen",
            ...     "email": "tenant@example.com",
            ...     "phone": "1234567890"
            ... })
        """
        try:
            # Check rate limit
            if not self.check_rate_limit():
                return False, "Too many requests. Please try again later."
            
            # Validate using Pydantic model
            request_data = MaintenanceRequestData(**data)
            
            # Additional custom validation if needed
            if request_data.urgent and not request_data.phone:
                return False, "Phone number required for urgent requests"
                
            logger.info(f"Request validation successful for property {request_data.property_id}")
            return True, ""
            
        except ValueError as e:
            logger.warning(f"Validation failed: {str(e)}")
            return False, str(e)
            
        except Exception as e:
            logger.error(f"Unexpected validation error: {str(e)}")
            return False, "Invalid request data"

    def validate_photo_url(self, url: str) -> bool:
        """Validate maintenance request photo URL for demo environment"""
        allowed_domains = ['s3.amazonaws.com', 'maintenance-photos.example.com']
        try:
            # Basic URL format validation
            if not re.match(r'https?://[^\s/$.?#].[^\s]*$', url):
                return False
                
            # Check allowed domains
            domain = re.search(r'https?://([^/]+)', url).group(1)
            return domain in allowed_domains
            
        except Exception as e:
            logger.error(f"URL validation failed: {str(e)}")
            return False