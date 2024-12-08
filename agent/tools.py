from typing import Dict, List, Optional, Any
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
import aiosmtplib
import asyncio

from app.database import Database
from app.config import get_settings
from utils.logger import setup_logger

logger = setup_logger("agent.tools", log_file="logs/tools.log")

class MaintenanceRequestError(Exception):
    """Custom exception for maintenance requests"""
    pass

class BaseMaintenanceTool(BaseTool, BaseModel):
    """Base class for maintenance tools"""
    
    ISSUE_CATEGORIES = ['plumbing', 'electrical', 'structural', 'appliance', 'hvac', 'other']
    PRIORITY_LEVELS = ['urgent', 'high', 'medium', 'low']
    
    settings: Any = Field(default_factory=get_settings)
    db: Any = Field(default=None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = Database(self.settings)

class IssueClassificationTool(BaseMaintenanceTool):
    """Analyzes maintenance issues"""
    
    name: str = "issue_classification"
    description: str = "Classify maintenance issues"
    llm: Optional[ChatOpenAI] = None
    
    def _run(self, description: str) -> Dict[str, Any]:
        """Classify maintenance issue"""
        try:
            if not self.llm:
                self.llm = ChatOpenAI(
                    model="gpt-4-1106-preview",
                    temperature=0
                )
            
            prompt = f"""
            Analyze this maintenance issue: {description}
            Provide a JSON response with:
            - category: {' | '.join(self.ISSUE_CATEGORIES)}
            - priority: {' | '.join(self.PRIORITY_LEVELS)}
            - estimated_hours: integer between 1-4
            """
            
            result = self.llm.predict(prompt)
            return eval(result)  # Safe for MVP as we control the prompt
            
        except Exception as e:
            logger.error(f"Classification failed: {str(e)}")
            raise MaintenanceRequestError("Unable to classify issue")

class ContractorBookingTool(BaseMaintenanceTool):
    """Books contractors for maintenance"""
    
    name: str = "contractor_booking"
    description: str = "Find and book contractors"
    
    # MVP: Fixed scheduling based on priority
    SCHEDULING_DEFAULTS = {
        'urgent': timedelta(hours=4),    # Within 4 hours
        'high': timedelta(days=1),       # Next day
        'medium': timedelta(days=3),     # Within 3 days
        'low': timedelta(days=5)         # Within 5 days
    }
    
    def _run(self, category: str, priority: str) -> Dict[str, Any]:
        """Simple contractor booking"""
        try:
            # Get first available contractor for category
            contractor = asyncio.run(self.db.fetch_one(
                "contractors",
                {"skills": category}
            ))
            
            if not contractor:
                return {"success": False, "error": "No contractor available"}
            
            # Set appointment time based on priority
            scheduled_time = datetime.now() + self.SCHEDULING_DEFAULTS[priority]
            
            return {
                "success": True,
                "booking": {
                    "contractor_name": contractor['name'],
                    "contractor_phone": contractor['phone'],
                    "scheduled_date": scheduled_time.strftime('%Y-%m-%d'),
                    "scheduled_time": scheduled_time.strftime('%H:%M'),
                    "category": category
                }
            }
            
        except Exception as e:
            logger.error(f"Booking failed: {str(e)}")
            raise MaintenanceRequestError("Unable to book contractor")

class NotificationTool(BaseMaintenanceTool):
    """Sends notifications to stakeholders"""
    
    name: str = "notification"
    description: str = "Send maintenance notifications"
    
    def _run(self, recipient: str, booking: Dict[str, Any], description: str) -> Dict[str, Any]:
        """Send simple notification email"""
        try:
            body = f"""
            Your maintenance request has been scheduled:
            
            Issue: {description}
            
            Appointment Details:
            Date: {booking['scheduled_date']}
            Time: {booking['scheduled_time']}
            
            Contractor: {booking['contractor_name']}
            Phone: {booking['contractor_phone']}
            
            Thank you for your patience.
            """
            
            msg = MIMEMultipart()
            msg.attach(MIMEText(body, 'plain'))
            msg['Subject'] = "Maintenance Request Scheduled"
            msg['To'] = recipient
            msg['From'] = self.settings.SMTP_USER
            
            asyncio.run(self._send_email(msg))
            
            return {"success": True, "recipient": recipient}
            
        except Exception as e:
            logger.error(f"Notification failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _send_email(self, msg: MIMEMultipart) -> None:
        """Send email"""
        async with aiosmtplib.SMTP(
            hostname=self.settings.SMTP_HOST,
            port=self.settings.SMTP_PORT,
            use_tls=True
        ) as server:
            await server.login(
                self.settings.SMTP_USER,
                self.settings.SMTP_PASSWORD.get_secret_value()
            )
            await server.send_message(msg)

class CostEstimationTool(BaseMaintenanceTool):
    """Estimates maintenance costs"""
    
    name: str = "cost_estimation"
    description: str = "Estimate maintenance costs"
    
    # MVP: Fixed costs per category
    FIXED_COSTS = {
        'plumbing': {'base': 200, 'urgent': 300},
        'electrical': {'base': 250, 'urgent': 375},
        'structural': {'base': 500, 'urgent': 750},
        'appliance': {'base': 150, 'urgent': 225},
        'hvac': {'base': 300, 'urgent': 450},
        'other': {'base': 200, 'urgent': 300}
    }
    
    def _run(self, category: str, priority: str) -> Dict[str, Any]:
        """Simple cost estimation"""
        try:
            costs = self.FIXED_COSTS.get(category, self.FIXED_COSTS['other'])
            estimate = costs['urgent'] if priority == 'urgent' else costs['base']
            
            return {
                "success": True,
                "estimate": estimate,
                "currency": "GBP"
            }
            
        except Exception as e:
            logger.error(f"Cost estimation failed: {str(e)}")
            raise MaintenanceRequestError("Unable to estimate cost")



# Add to existing tools.py - added job report generation tool. 

class CompletionReportTool(BaseMaintenanceTool):
    """Tool for generating contextual completion reports"""
    
    name: str = "completion_report"
    description: str = "Generate maintenance completion reports"
    
    # Standard labor rates for demo
    LABOR_RATES = {
        'plumbing': 75,
        'electrical': 85,
        'hvac': 90,
        'general': 65,
        'emergency': 100
    }
    
    # Common parts and costs by category
    COMMON_PARTS = {
        'plumbing': [
            ('Pipe fitting kit', 25),
            ('Sink gasket set', 15),
            ('Water valve', 35),
            ('Pipe sealant', 10)
        ],
        'electrical': [
            ('Circuit breaker', 40),
            ('Outlet', 12),
            ('Wiring kit', 30),
            ('Junction box', 15)
        ],
        'hvac': [
            ('Air filter', 20),
            ('Refrigerant', 45),
            ('Thermostat', 85),
            ('Duct tape', 8)
        ],
        'general': [
            ('Hardware set', 15),
            ('Sealant', 10),
            ('Basic supplies', 20)
        ]
    }
    
    def _run(self, 
             description: str,
             category: str,
             priority: str,
             actual_hours: Optional[float] = None) -> Dict[str, Any]:
        """
        Generate completion report based on request details.
        
        Args:
            description: Original maintenance request description
            category: Type of maintenance work
            priority: Request priority level
            actual_hours: Optional actual hours spent (for demo flexibility)
        
        Returns:
            Dictionary containing completion details
        """
        try:
            # Generate contextual work notes
            work_performed = self._generate_work_notes(description, category)
            
            # Select relevant parts used
            parts_used, parts_cost = self._select_parts(category)
            
            # Calculate labor
            labor_hours = actual_hours or self._estimate_labor_hours(category, priority)
            labor_rate = self.LABOR_RATES.get(category, self.LABOR_RATES['general'])
            if priority == 'urgent':
                labor_rate = self.LABOR_RATES['emergency']
            
            labor_cost = labor_hours * labor_rate
            
            # Prepare report
            return {
                "success": True,
                "completion_report": {
                    "work_performed": work_performed,
                    "parts_used": parts_used,
                    "labor_hours": labor_hours,
                    "costs": {
                        "labor": labor_cost,
                        "parts": parts_cost,
                        "total": labor_cost + parts_cost
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to generate completion report: {str(e)}")
            return {
                "success": False,
                "error": "Could not generate completion report"
            }

    def _generate_work_notes(self, description: str, category: str) -> str:
        """Generate contextual work notes based on the issue"""
        # Extract key terms from description
        description_lower = description.lower()
        
        if category == 'plumbing':
            if 'leak' in description_lower:
                return ("Located and repaired water leak. Replaced worn seals and "
                       "fittings. Pressure tested system and confirmed resolution.")
            if 'drain' in description_lower:
                return ("Cleared blocked drain line using professional equipment. "
                       "Inspected pipes for damage and cleaned access points.")
                
        elif category == 'electrical':
            if 'outlet' in description_lower:
                return ("Tested circuit and replaced faulty outlet. Verified proper "
                       "grounding and checked nearby connections.")
            if 'light' in description_lower:
                return ("Diagnosed electrical issue, repaired wiring connection. "
                       "Tested fixture operation and confirmed safety.")
                
        elif category == 'hvac':
            if 'cooling' in description_lower or 'ac' in description_lower:
                return ("Serviced AC unit, cleaned components, and recharged system. "
                       "Tested cooling operation and verified proper function.")
            if 'heat' in description_lower:
                return ("Inspected heating system, cleaned components, and calibrated "
                       "controls. Confirmed proper heat output and safety systems.")
        
        # Default general maintenance note
        return ("Completed maintenance work as requested. Tested all affected "
               "systems and verified proper operation.")

    def _select_parts(self, category: str) -> Tuple[str, float]:
        """Select relevant parts based on category"""
        parts_list = self.COMMON_PARTS.get(category, self.COMMON_PARTS['general'])
        # Select 1-3 relevant parts for demo
        selected = random.sample(parts_list, min(random.randint(1, 3), len(parts_list)))
        
        parts_text = ", ".join(part[0] for part in selected)
        total_cost = sum(part[1] for part in selected)
        
        return parts_text, total_cost

    def _estimate_labor_hours(self, category: str, priority: str) -> float:
        """Estimate labor hours based on job type"""
        base_hours = {
            'plumbing': 1.5,
            'electrical': 2.0,
            'hvac': 2.5,
            'general': 1.0
        }.get(category, 1.0)
        
        # Adjust for priority
        if priority == 'urgent':
            base_hours *= 0.8  # Emergency jobs typically faster
        elif priority == 'low':
            base_hours *= 1.2  # Low priority might involve multiple visits
            
        return round(base_hours, 1)



# Initialize tools
MAINTENANCE_TOOLS: Dict[str, BaseTool] = {}

def initialize_tools() -> Dict[str, BaseTool]:
    """Initialize MVP tools"""
    global MAINTENANCE_TOOLS
    try:
        MAINTENANCE_TOOLS = {
            'issue_classification': IssueClassificationTool(),
            'contractor_booking': ContractorBookingTool(),
            'notification': NotificationTool(),
            'cost_estimation': CostEstimationTool(),
            'completion_report': CompletionReportTool() 
        }
        return MAINTENANCE_TOOLS
    except Exception as e:
        logger.error(f"Tool initialization failed: {str(e)}")
        raise MaintenanceRequestError("Tool setup failed")



def get_tool(tool_name: str) -> BaseTool:
    """Get tool instance"""
    if tool_name not in MAINTENANCE_TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return MAINTENANCE_TOOLS[tool_name]

# Initialize tools
initialize_tools()