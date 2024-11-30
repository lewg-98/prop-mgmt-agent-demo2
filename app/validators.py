import re
from typing import Tuple, Dict
import bleach
from datetime import datetime, timedelta

class RequestValidator:
    def __init__(self):
        self._setup_rate_limits()
    
    def _setup_rate_limits(self):
        self.request_times = []
        self.max_requests = 10
        self.time_window = 60  # seconds
    
    def validate_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def validate_phone(self, phone: str) -> bool:
        pattern = r'^\+?1?\d{9,15}$'
        return bool(re.match(pattern, phone))
    
    def sanitize_input(self, text: str) -> str:
        return bleach.clean(text)
    
    def check_rate_limit(self) -> bool:
        now = datetime.now()
        self.request_times = [t for t in self.request_times 
                            if now - t < timedelta(seconds=self.time_window)]
        if len(self.request_times) >= self.max_requests:
            return False
        self.request_times.append(now)
        return True
    
    def validate_request(self, data: Dict) -> Tuple[bool, str]:
        if not self.check_rate_limit():
            return False, "Too many requests. Please try again later."
        
        if not data.get('property_id'):
            return False, "Property selection is required."
            
        description = self.sanitize_input(data.get('description', ''))
        if len(description.strip()) < 10:
            return False, "Description must be at least 10 characters."
            
        if not self.validate_email(data.get('email', '')):
            return False, "Invalid email address."
            
        if not self.validate_phone(data.get('phone', '')):
            return False, "Invalid phone number."
            
        return True, ""