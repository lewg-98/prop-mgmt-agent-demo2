from langchain.tools import BaseTool
from typing import Dict, List, Optional, Any, Tuple, ClassVar
from langchain_openai import ChatOpenAI
import json
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from retry import retry
import logging
from datetime import datetime, timedelta
from app.database import Database
from app.config import get_settings
from pydantic import Field

# Configure logging
logger = logging.getLogger(__name__)

class MaintenanceRequestError(Exception):
    """Custom exception for maintenance request handling"""
    pass

# Base maintenance tool with shared functionality
class BaseMaintenanceTool(BaseTool):
    """Base class for maintenance tools with shared configurations"""
    
    ISSUE_CATEGORIES: ClassVar[List[str]] = ['plumbing', 'electrical', 'structural', 'appliance', 'hvac', 'other']
    PRIORITY_LEVELS: ClassVar[List[str]] = ['urgent', 'high', 'medium', 'low']
    settings: Any = Field(default=None)
    db: Any = Field(default=None)
    
    def __init__(self):
        """Initialize shared components"""
        super().__init__()
        self.settings = get_settings()
        self.db = Database(self.settings)

class IssueClassificationTool(BaseMaintenanceTool):
    """Tool for classifying maintenance issues using AI"""
    
    name: str = Field(default="issue_classification")
    description: str = Field(default="Classify maintenance issues by type, priority, and estimated effort")
    llm: Optional[ChatOpenAI] = Field(default=None)
    
    def _setup_llm(self) -> None:
        """Set up language model for classification"""
        self.llm = ChatOpenAI(
            model="gpt-4-1106-preview",
            temperature=0,
            cache=True,
            max_retries=3,
            request_timeout=30
        )

    def _run(self, description: str) -> Dict[str, Any]:
        """
        Classify a maintenance issue based on its description.
        
        Args:
            description: Detailed description of the maintenance issue
            
        Returns:
            Dictionary containing classification details including category, priority, etc.
        """
        try:
            self._setup_llm()
            
            # Create detailed analysis prompt
            prompt = f"""
            Analyze this maintenance issue: {description}
            
            Provide a JSON response with:
            - category: {' | '.join(self.ISSUE_CATEGORIES)}
            - priority: {' | '.join(self.PRIORITY_LEVELS)}
            - estimated_hours: integer between 1 and 8
            - risk_level: low | medium | high
            - requires_license: boolean
            - estimated_cost_range: low (<£300) | medium (£300-$1000) | high (>£1000)
            """
            
            response = self.llm.predict(prompt)
            classification = json.loads(response)
            
            # Validate response
            required_fields = ['category', 'priority', 'estimated_hours']
            if not all(field in classification for field in required_fields):
                raise ValueError("Incomplete classification response")
            
            logger.info(f"Issue classified: {classification['category']} - {classification['priority']}")
            return classification
            
        except Exception as e:
            logger.error(f"Issue classification failed: {str(e)}")
            raise MaintenanceRequestError("Failed to classify issue") from e

class ContractorBookingTool(BaseMaintenanceTool):
    """Tool for finding and booking contractors"""
    
    name: str = Field(default="contractor_booking")
    description: str = Field(default="Find and book available contractors for maintenance work")
    
    @retry(tries=3, delay=1, backoff=2)
    def _run(self, category: str, hours: int, emergency: bool = False, start_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Find and book available contractors.
        
        Args:
            category: Type of maintenance work needed
            hours: Estimated hours required
            emergency: Whether this is an emergency request
            
        Returns:
            Dictionary containing matched contractors and booking details
        """
        try:
            # Find available contractors
            contractors = asyncio.run(self.db.fetch_all(
                "contractors",
                {
                    "skills": category,
                    "hours_available": {"gte": hours},
                    "emergency_available": emergency,
                    "availability_windows": {
                        "start_date": start_date or datetime.now(),
                        "required_hours": hours
                    }
                }
            ))
            
            if not contractors:
                return {"success": False, "error": "No contractors available"}
            
            # Add booking timestamp for concurrency control
            for contractor in contractors:
                contractor['query_timestamp'] = datetime.now()
            
            return {
                "success": True,
                "contractors": contractors[:5],
                "booking_available": True,
                "valid_until": datetime.now() + timedelta(minutes=15)
            }
            
        except Exception as e:
            logger.error(f"Contractor booking failed: {str(e)}")
            raise MaintenanceRequestError("Failed to book contractor") from e

class EmailNotificationTool(BaseMaintenanceTool):
    """Tool for sending email notifications"""
    
    name: str = Field(default="email_notification")
    description: str = Field(default="Send email notifications to stakeholders")
    
    @retry(tries=3, delay=1, backoff=2)
    def _run(self, recipient: str, subject: str, body: str, priority: str = 'normal') -> Dict[str, Any]:
        """
        Send email notifications to stakeholders.
        
        Args:
            recipient: Email recipient address
            subject: Email subject line
            body: Email content
            priority: Message priority level
            
        Returns:
            Dictionary indicating success or failure of sending notification
        """
        try:
            # Create email message
            msg = MIMEMultipart()
            msg.attach(MIMEText(body, 'plain'))
            
            # Add headers
            msg['Subject'] = f"[{priority.upper()}] {subject}" if priority == 'high' else subject
            msg['From'] = self.settings.SMTP_USER
            msg['To'] = recipient
            msg['X-Priority'] = '1' if priority == 'high' else '3'
            
            # Send email
            asyncio.run(self._send_email(msg))
            
            logger.info(f"Notification sent to {recipient}")
            return {"success": True, "recipient": recipient}
            
        except Exception as e:
            logger.error(f"Email notification failed: {str(e)}")
            raise MaintenanceRequestError("Failed to send notification") from e
    
    async def _send_email(self, msg: MIMEMultipart) -> None:
        """Handle actual email sending"""
        async with aiosmtplib.SMTP(
            hostname=self.settings.SMTP_HOST,
            port=self.settings.SMTP_PORT,
            use_tls=True,
            timeout=30
        ) as server:
            await server.login(
                self.settings.SMTP_USER,
                self.settings.SMTP_PASSWORD.get_secret_value()
            )
            await server.send_message(msg)

class PropertyLookupTool(BaseMaintenanceTool):
    """Tool for retrieving property information"""
    
    name: str = Field(default="property_lookup")
    description: str = Field(default="Look up property details and maintenance history")
    
    def _run(self, property_id: str) -> Dict[str, Any]:
        """
        Retrieve property information and maintenance history.
        
        Args:
            property_id: Unique identifier for the property
            
        Returns:
            Dictionary containing property details and maintenance history
        """
        try:
            # Get property details
            property_data = asyncio.run(self.db.fetch_one(
                "properties",
                {"id": property_id}
            ))
            
            if not property_data:
                return {"success": False, "error": "Property not found"}
            
            # Get maintenance history
            maintenance_history = asyncio.run(self.db.fetch_all(
                "maintenance_requests",
                {"property_id": property_id}
            ))
            
            return {
                "success": True,
                "property": property_data,
                "maintenance_history": maintenance_history
            }
            
        except Exception as e:
            logger.error(f"Property lookup failed: {str(e)}")
            raise MaintenanceRequestError("Failed to retrieve property information") from e

class CostEstimationTool(BaseMaintenanceTool):
    """Tool for estimating maintenance costs"""
    
    name: str = Field(default="cost_estimation")
    description: str = Field(default="Estimate costs for maintenance work based on issue type and property details")
    
    # Cost reference data (in a real system, this would come from a database)
    BASE_COSTS: ClassVar[Dict[str, Dict[str, int]]] = {
        'plumbing': {'low': 150, 'medium': 500, 'high': 1500},
        'electrical': {'low': 200, 'medium': 600, 'high': 2000},
        'structural': {'low': 500, 'medium': 2000, 'high': 5000},
        'appliance': {'low': 100, 'medium': 400, 'high': 1200},
        'hvac': {'low': 250, 'medium': 800, 'high': 3000},
        'other': {'low': 200, 'medium': 500, 'high': 1500}
    }

    def _run(self, category: str, description: str, property_type: str = 'standard') -> Dict[str, Any]:
        """
        Estimate maintenance costs based on issue details.
        
        Args:
            category: Type of maintenance issue
            description: Detailed description of the issue
            property_type: Type of property (standard, luxury, etc.)
            
        Returns:
            Dictionary containing cost estimates and confidence levels
        """
        try:
            # Get base cost range for category
            base_costs = self.BASE_COSTS.get(category, self.BASE_COSTS['other'])
            
            # Analyze description for complexity
            complexity_factor = self._analyze_complexity(description)
            
            # Adjust for property type
            property_factor = 1.5 if property_type == 'luxury' else 1.0
            
            # Calculate estimates
            estimates = {
                'low': base_costs['low'] * complexity_factor * property_factor,
                'medium': base_costs['medium'] * complexity_factor * property_factor,
                'high': base_costs['high'] * complexity_factor * property_factor
            }
            
            # Add confidence level based on available information
            confidence = self._calculate_confidence(category, description)
            
            return {
                "success": True,
                "estimates": {
                    "low_end": round(estimates['low'], 2),
                    "typical": round(estimates['medium'], 2),
                    "high_end": round(estimates['high'], 2)
                },
                "confidence": confidence,
                "factors_considered": {
                    "base_category": category,
                    "complexity": complexity_factor,
                    "property_type": property_type
                }
            }
            
        except Exception as e:
            logger.error(f"Cost estimation failed: {str(e)}")
            raise MaintenanceRequestError("Failed to estimate costs") from e

    def _analyze_complexity(self, description: str) -> float:
        """
        Analyze issue complexity from description.
        Returns a multiplier for the base cost.
        """
        # Simple complexity analysis based on keywords
        complexity_indicators = {
            'emergency': 1.5,
            'urgent': 1.3,
            'multiple': 1.4,
            'extensive': 1.4,
            'simple': 0.8,
            'minor': 0.7,
            'quick': 0.6
        }
        
        description = description.lower()
        multiplier = 1.0
        
        for indicator, factor in complexity_indicators.items():
            if indicator in description:
                multiplier *= factor
        
        return max(0.5, min(multiplier, 2.0))  # Cap multiplier between 0.5 and 2.0

    def _calculate_confidence(self, category: str, description: str) -> float:
        """
        Calculate confidence level in estimate.
        Returns a value between 0 and 1.
        """
        confidence = 0.7  # Base confidence level
        
        # Adjust based on category
        if category in self.BASE_COSTS:
            confidence += 0.1
            
        # Adjust based on description detail
        word_count = len(description.split())
        if word_count > 50:
            confidence += 0.1
        elif word_count < 10:
            confidence -= 0.1
            
        return round(max(0.3, min(confidence, 0.9)), 2)  # Cap between 0.3 and 0.9

# Tool registry for easy access
MAINTENANCE_TOOLS = {
    'issue_classification': IssueClassificationTool(),
    'contractor_booking': ContractorBookingTool(),
    'email_notification': EmailNotificationTool(),
    'property_lookup': PropertyLookupTool(),
    'cost_estimation': CostEstimationTool()
}

def get_tool(tool_name: str) -> BaseTool:
    """
    Get a specific tool instance.
    
    Args:
        tool_name: Name of the tool to retrieve
        
    Returns:
        Initialized tool instance
    """
    if tool_name not in MAINTENANCE_TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return MAINTENANCE_TOOLS[tool_name]


class MaintenanceTools:
    """Wrapper class for all maintenance tools"""
    def __init__(self):
        self.issue_classification = IssueClassificationTool()
        self.contractor_booking = ContractorBookingTool()
        self.email_notification = EmailNotificationTool()
        self.property_lookup = PropertyLookupTool()
        self.cost_estimation = CostEstimationTool()