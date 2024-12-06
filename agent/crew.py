from typing import Dict, List, Optional, Any
from crewai import Agent, Task, Crew, Process
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import logging
from datetime import datetime, timedelta
from enum import Enum
import asyncio

# Import our enhanced tools
from .tools import (
    get_tool,
    MAINTENANCE_TOOLS,
    MaintenanceRequestError
)
from app.config import Settings

# Configure logging
logger = logging.getLogger(__name__)

class RequestPriority(Enum):
    """Maintenance request priority levels"""
    EMERGENCY = "emergency"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class RequestStatus(Enum):
    """Maintenance request status states"""
    NEW = "new"
    ANALYZING = "analyzing"
    COORDINATING = "coordinating"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    FAILED = "failed"

class MaintenanceRequest(BaseModel):
    """
    Schema for maintenance request data with validation.
    Tracks the complete lifecycle of a maintenance request.
    """
    id: str
    property_id: str
    description: str
    contact_email: Optional[str]
    contact_phone: Optional[str]
    photo_url: Optional[str]
    status: RequestStatus = Field(default=RequestStatus.NEW)
    priority: Optional[RequestPriority]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_cost: Optional[float]
    scheduled_time: Optional[datetime]
    assigned_contractor: Optional[str]

    class Config:
        use_enum_values = True

class DomiCrew:
    """
    AI Crew orchestrator for maintenance request handling.
    Coordinates multiple AI agents to process maintenance requests.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize the AI crew with proper configuration.
        
        Args:
            settings: Application configuration settings
        """
        self.settings = settings
        self.tools = self._initialize_tools()
        self.agents = self._initialize_agents()
        logger.info("DomiCrew initialized successfully")

    def _initialize_tools(self) -> Dict[str, BaseTool]:
        """
        Initialize AI tools with proper error handling.
        Tools are specialized for different maintenance tasks.
        """
        try:
            # Initialize all required tools from our registry
            return {
                "analysis": [
                    get_tool("issue_classification"),
                    get_tool("cost_estimation"),
                    get_tool("property_lookup")
                ],
                "coordination": [
                    get_tool("contractor_booking"),
                    get_tool("email_notification")
                ]
            }
            
        except Exception as e:
            logger.error(f"Tool initialization failed: {str(e)}")
            raise MaintenanceRequestError("Failed to initialize AI tools") from e

    def _initialize_agents(self) -> Dict[str, Agent]:
        """
        Initialize specialized AI agents with specific roles.
        Each agent has dedicated tools and responsibilities.
        """
        try:
            agents = {
                "analyzer": Agent(
                    role="Maintenance Request Analyzer",
                    goal="Analyze and prioritize maintenance requests accurately",
                    backstory="""Expert maintenance analyst with deep knowledge of 
                    building systems and emergency protocols. Specializes in risk 
                    assessment and cost estimation.""",
                    tools=self.tools["analysis"],
                    verbose=self.settings.ENV == "development",
                    allow_delegation=True
                ),
                "coordinator": Agent(
                    role="Maintenance Coordinator",
                    goal="Coordinate maintenance activities efficiently",
                    backstory="""Experienced maintenance coordinator with expertise 
                    in contractor management and emergency response. Ensures fast, 
                    effective resolution of maintenance issues.""",
                    tools=self.tools["coordination"],
                    verbose=self.settings.ENV == "development",
                    allow_delegation=True
                )
            }
            logger.info("AI agents initialized successfully")
            return agents
            
        except Exception as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            raise MaintenanceRequestError("Failed to initialize AI agents") from e

    async def handle_maintenance_request(self, request: MaintenanceRequest) -> Dict[str, Any]:
        """
        Process a maintenance request through the AI crew.
        Coordinates analysis and resolution through specialized agents.
        
        Args:
            request: Complete maintenance request details
            
        Returns:
            Dictionary containing processing results and status
        """
        logger.info(f"Processing maintenance request {request.id}")
        
        try:
            # Update request status
            request.status = RequestStatus.ANALYZING
            
            # Create analysis task with detailed instructions
            analysis_task = Task(
                description=f"""
                Analyze maintenance request for property {request.property_id}:
                1. Use issue_classification tool to categorize the issue
                2. Use property_lookup tool to get property context
                3. Use cost_estimation tool to estimate repair costs
                4. Determine priority and safety implications
                
                Request Details:
                - Description: {request.description}
                - Photos: {request.photo_url if request.photo_url else 'None provided'}
                
                Provide detailed analysis in JSON format.
                """,
                agent=self.agents["analyzer"],
                expected_output="JSON containing analysis results"
            )

            # Create coordination task based on analysis
            coordination_task = Task(
                description=f"""
                Coordinate maintenance resolution based on analysis results:
                1. Use contractor_booking tool to find and book contractor
                2. Use email_notification tool to send updates to:
                   - Contact Email: {request.contact_email}
                   - Contact Phone: {request.contact_phone}
                3. Schedule work and confirm arrangements
                4. Send confirmation notifications
                
                Provide coordination details in JSON format.
                """,
                agent=self.agents["coordinator"],
                expected_output="JSON containing coordination results"
            )

            # Create and execute crew
            crew = Crew(
                agents=list(self.agents.values()),
                tasks=[analysis_task, coordination_task],
                process=Process.sequential,
                verbose=self.settings.ENV == "development"
            )

            # Execute crew tasks
            result = await crew.kickoff()
            
            # Update request with results
            request.status = RequestStatus.SCHEDULED
            request.updated_at = datetime.utcnow()
            
            logger.info(f"Successfully processed request {request.id}")
            return {
                "success": True,
                "request_id": request.id,
                "status": request.status,
                "result": result,
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to process request {request.id}: {str(e)}")
            request.status = RequestStatus.FAILED
            raise MaintenanceRequestError(f"Request processing failed: {str(e)}") from e

    async def get_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed status of all agents and their current tasks.
        
        Returns:
            Dictionary containing status for each agent
        """
        try:
            status = {}
            for name, agent in self.agents.items():
                status[name] = {
                    "status": "active" if agent.is_available() else "busy",
                    "last_active": datetime.utcnow().isoformat(),
                    "current_task": agent.current_task.description if agent.current_task else None,
                    "tools_available": [tool.name for tool in agent.tools]
                }
            return status
        except Exception as e:
            logger.error(f"Failed to get agent status: {str(e)}")
            raise MaintenanceRequestError("Unable to retrieve agent status") from e

    async def reset_agents(self) -> None:
        """
        Reset all agents to their initial state.
        Useful for clearing any stuck tasks or states.
        """
        try:
            for agent in self.agents.values():
                agent.current_task = None
            logger.info("Agents reset successfully")
        except Exception as e:
            logger.error(f"Failed to reset agents: {str(e)}")
            raise MaintenanceRequestError("Unable to reset agents") from e