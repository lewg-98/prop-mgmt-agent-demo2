from typing import Tuple, Dict, Optional, List
import bleach # type: ignore
from utils.logger import setup_logger
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator # type: ignore
from datetime import datetime
from enum import Enum

# Configure logger
logger = setup_logger("app.validators", log_file="logs/validation.log")

class MaintenanceRequestData(BaseModel):
    """
    Simplified maintenance request validation for MVP demo.
    Focuses on essential validations with demo-friendly responses.
    """
    property_id: str
    description: str = Field(..., min_length=10, max_length=1000)
    email: EmailStr
    phone: Optional[str] = None
    urgent: bool = Field(default=False)
    photo_urls: Optional[List[str]] = None

    model_config = ConfigDict(
        error_msg_templates = {
            'value_error.missing': '⚠️ {field_name} is required',
            'value_error.any_str.min_length': '⚠️ Please provide more details about the issue',
            'value_error.any_str.max_length': '⚠️ Description is too long (max 1000 characters)',
            'value_error.email': '⚠️ Please provide a valid email address'
        }
    )

    @model_validator(mode='after')
    def validate_urgent_phone(self) -> 'MaintenanceRequestData':
        """Validate phone number is provided for urgent requests"""
        if self.urgent and not self.phone:
            raise ValueError("Phone number required for urgent requests")
        return self

class RequestValidator:
    """
    Simplified validator for MVP demo.
    Handles basic input validation with user-friendly messages.
    """
    
    def __init__(self, max_description_length: int = 1000):
        """Initialize validator with basic configuration"""
        self.max_description_length = max_description_length
        logger.info("Request validator initialized")

    def sanitize_input(self, text: str) -> str:
        """
        Basic input sanitization for security.
        
        Args:
            text: Raw input text
            
        Returns:
            Cleaned text string
        """
        try:
            return bleach.clean(text, strip=True)
        except Exception as e:
            logger.error(f"Input sanitization failed: {str(e)}")
            raise ValueError("⚠️ Invalid input text") from e

    def validate_request(self, data: Dict) -> Tuple[bool, str]:
        """
        Validate maintenance request with demo-friendly messages.
        
        Args:
            data: Request data dictionary
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            # Sanitize description if present
            if 'description' in data:
                data['description'] = self.sanitize_input(data['description'])
            
            # Validate using Pydantic model
            request_data = MaintenanceRequestData.model_validate(data)
            
            # Demo-specific validations
            if request_data.urgent and not request_data.phone:
                return False, "⚠️ Please provide a phone number for urgent requests"
                
            if len(request_data.description.strip()) < 10:
                return False, "⚠️ Please provide more details about the issue"
                
            logger.info(f"Request validation successful for property {request_data.property_id}")
            return True, "✅ Request validation successful"
            
        except Exception as e:
            logger.warning(f"Validation failed: {str(e)}")
            return False, f"⚠️ Please check your input: {str(e)}"

    def validate_photo_url(self, url: str) -> bool:
        """
        Basic URL validation for demo purposes.
        
        Args:
            url: Photo URL to validate
            
        Returns:
            Boolean indicating if URL is valid
        """
        return url.startswith(('http://', 'https://')) if url else False