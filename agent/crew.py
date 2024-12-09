from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from enum import Enum
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from app.database import Database

from .tools import (
    MAINTENANCE_TOOLS,
    MaintenanceRequestError
)
from app.config import Settings
from utils.logger import setup_logger

# Configure logging
logger = setup_logger("agent.crew", log_file="logs/crew.log")

class RequestStatus(str, Enum):
    """Simple status states for demo clarity"""
    NEW = "new"
    PROCESSING = "processing" 
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    FAILED = "failed"

class MaintenanceRequest(BaseModel):
    """Simplified maintenance request model for MVP"""
    id: str
    property_id: str
    description: str
    contact_email: str
    contact_phone: Optional[str] = None
    photo_url: Optional[str] = None
    status: RequestStatus = Field(default=RequestStatus.NEW)
    priority: Optional[str] = None  # Simple string: urgent, high, medium, low
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scheduled_time: Optional[datetime] = None
    assigned_contractor: Optional[str] = None
    completion_details: Optional[Dict] = None  # Added for completion report

class DomiCrew:
    """
    Simplified AI Crew for maintenance request handling.
    Focuses on core demo workflow with single agent approach.
    """
    
    def __init__(self, settings: Settings):
        """Initialize with minimal required components"""
        self.settings = settings
        self.llm = ChatOpenAI(
            model="gpt-4-1106-preview",
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY.get_secret_value()
        )
        self.db = Database(settings) 
        self.agent = self._initialize_agent()
        logger.info("DomiCrew initialized")

    def _initialize_agent(self) -> Agent:
        """Initialize single agent with essential tools"""
        try:
            return Agent(
                role="Maintenance Manager",
                goal="Process maintenance requests efficiently and accurately",
                backstory="""Expert maintenance coordinator with deep knowledge of 
                building systems and contractor management. Handles end-to-end 
                maintenance request processing.""",
                tools=[
                    MAINTENANCE_TOOLS['issue_classification'],
                    MAINTENANCE_TOOLS['contractor_booking'],
                    MAINTENANCE_TOOLS['notification'],
                    MAINTENANCE_TOOLS['cost_estimation'],
                    MAINTENANCE_TOOLS['completion_report']  # Added completion tool
                ],
                llm=self.llm,
                verbose=self.settings.ENV == "development"
            )
        except Exception as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            raise MaintenanceRequestError("Setup failed - please try again")

    async def handle_maintenance_request(self, request: MaintenanceRequest) -> Dict[str, Any]:
        """
        Process maintenance request with simple, linear flow.
        Provides clear status updates for demo visualization.
        """
        try:
            logger.info(f"Processing request {request.id}")
            
            # Start a database transaction
            async with self.db.transaction() as txn:
                # Update status in database and local object atomically
                request.status = RequestStatus.PROCESSING
                await self.db.update("maintenance_requests", request.id, {
                    "status": RequestStatus.PROCESSING,
                    "updated_at": datetime.utcnow()
                })

                # Create and execute task
                task = Task(
                    description=f"""
                    Handle maintenance request for property {request.property_id}:

                    Request Details:
                    - Description: {request.description}
                    - Contact Email: {request.contact_email}
                    - Contact Phone: {request.contact_phone or 'Not provided'}
                    - Photo Available: {'Yes' if request.photo_url else 'No'}

                    Required Steps:
                    1. Analyze issue and classify into one of these categories:
                       plumbing, electrical, structural, appliance, hvac, or other

                    2. Determine priority level:
                       urgent, high, medium, or low

                    3. Use cost estimation tool to calculate repair costs based on category

                    4. Find and schedule appropriate contractor for the classified category

                    5. Send confirmation to contact email

                    Provide results in JSON format with:
                    - issue_type: must be one of [plumbing, electrical, structural, appliance, hvac, other]
                    - priority: must be one of [urgent, high, medium, low]
                    - estimated_cost: will be calculated based on issue_type and priority
                    - contractor_name: string
                    - scheduled_time: datetime string
                    - safety_notes: string (if applicable)
                    - next_steps: string
                    """,
                    agent=self.agent
                )

                crew = Crew(
                    agents=[self.agent],
                    tasks=[task],
                    process=Process.sequential,
                    verbose=self.settings.ENV == "development"
                )

                result = await crew.kickoff()

                # Update both database and local object with results atomically
                request.status = RequestStatus.SCHEDULED
                request.priority = result.get('priority')
                request.scheduled_time = result.get('scheduled_time')
                request.assigned_contractor = result.get('contractor_name')

                await self.db.update("maintenance_requests", request.id, {
                    "status": RequestStatus.SCHEDULED,
                    "priority": result.get('priority'),
                    "category": result.get('issue_type'),
                    "estimated_cost": result.get('estimated_cost'),
                    "scheduled_time": result.get('scheduled_time'),
                    "assigned_contractor_id": result.get('contractor_id'),
                    "updated_at": datetime.utcnow()
                })

            logger.info(f"Request {request.id} processed successfully")
            return {
                "success": True,
                "request_id": request.id,
                "status": request.status,
                "priority": request.priority,
                "contractor": request.assigned_contractor,
                "scheduled_time": request.scheduled_time,
                "estimated_cost": result.get('estimated_cost'),
                "issue_type": result.get('issue_type'),
                "next_steps": result.get('next_steps'),
                "safety_notes": result.get('safety_notes', '')
            }

        except Exception as e:
            logger.error(f"Request processing failed: {str(e)}")
            # Ensure both database and local object reflect failure state
            request.status = RequestStatus.FAILED
            await self.db.update("maintenance_requests", request.id, {
                "status": RequestStatus.FAILED,
                "updated_at": datetime.utcnow()
            })
            return {
                "success": False,
                "error": "Processing failed - please try again",
                "details": str(e)
            }

    async def complete_request(self, request_id: str) -> Dict[str, Any]:
        """
        Generate completion report for a maintenance request.
        Uses AI to create contextual completion details.
        """
        try:
            # Fetch request from database
            request = await self.db.fetch_one("maintenance_requests", {"id": request_id})
            if not request:
                raise MaintenanceRequestError("Request not found")
            
            # No validation of request['description'], request['category'], etc.
            report = completion_tool.run(
                description=request['description'],
                category=request['category'],
                priority=request['priority']
            )

            if report['success']:
                # Update database with completion details
                await self.db.update("maintenance_requests", request_id, {
                    "status": RequestStatus.COMPLETED,
                    "completion_details": report['completion_report'],
                    "updated_at": datetime.utcnow()
                })

                return {
                    "success": True,
                    "request_id": request_id,
                    "completion_details": report['completion_report']
                }

            raise MaintenanceRequestError("Failed to generate completion report")

        except Exception as e:
            # Update database on failure
            await self.db.update("maintenance_requests", request_id, {
                "status": RequestStatus.FAILED,
                "updated_at": datetime.utcnow()
            })
            logger.error(f"Request processing failed: {str(e)}")
            
            return {
                "success": False,
                "error": "Processing failed - please try again",
                "details": str(e)
            }
        
        
    async def get_agent_status(self) -> Dict[str, Any]:
        """Simple status check for demo monitoring"""
        try:
            return {
                "status": "active" if self.agent is not None else "inactive",
                "last_check": datetime.utcnow().isoformat(),
                "tools_available": len(self.agent.tools)
            }
        except Exception as e:
            logger.error(f"Status check failed: {str(e)}")
            return {"status": "error", "error": str(e)}