from typing import Dict, Optional, Any
import asyncio
import logging
from datetime import datetime
from pydantic import ValidationError

from .crew import DomiCrew, MaintenanceRequest, RequestStatus, CrewError
from app.config import Settings, get_settings
from utils.logger import setup_logger

# Configure logger
logger = setup_logger("agent.main", log_file="logs/agent.log")

class MaintenanceAgent:
    """
    Main entry point for the Domi AI maintenance agent system.
    Handles request processing, status tracking, and error management.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the maintenance agent with configuration.
        
        Args:
            settings: Optional application settings, will use default if not provided
        """
        self.settings = settings or get_settings()
        self.crew = DomiCrew(self.settings)
        self.active_requests: Dict[str, MaintenanceRequest] = {}
        logger.info("Maintenance agent initialized successfully")
        
    async def process_request(self, 
                            request_data: Dict[str, Any],
                            priority_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a new maintenance request through the AI system.
        
        Args:
            request_data: Dictionary containing request details
            priority_override: Optional priority level to override AI assessment
            
        Returns:
            Dictionary containing processing results and status
            
        Example:
            >>> request = {
            ...     "property_id": "123",
            ...     "description": "Water leak in kitchen",
            ...     "contact_email": "tenant@example.com"
            ... }
            >>> result = await agent.process_request(request)
        """
        try:
            # Create and validate request object
            request = MaintenanceRequest(
                id=f"REQ-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
                **request_data
            )
            
            # Store active request
            self.active_requests[request.id] = request
            
            # Process through crew
            result = await self.crew.handle_maintenance_request(request)
            
            # Update request status
            self.active_requests[request.id] = request
            
            logger.info(f"Successfully processed request {request.id}")
            return {
                "success": True,
                "request_id": request.id,
                "status": request.status,
                "details": result
            }
            
        except ValidationError as e:
            logger.error(f"Invalid request data: {str(e)}")
            return {
                "success": False,
                "error": "Invalid request data",
                "details": str(e)
            }
            
        except CrewError as e:
            logger.error(f"Crew processing error: {str(e)}")
            return {
                "success": False,
                "error": "Processing failed",
                "details": str(e)
            }
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                "success": False,
                "error": "System error",
                "details": "An unexpected error occurred"
            }

    async def get_request_status(self, request_id: str) -> Dict[str, Any]:
        """
        Get current status of a maintenance request.
        
        Args:
            request_id: ID of the request to check
            
        Returns:
            Dictionary containing current status and details
        """
        try:
            request = self.active_requests.get(request_id)
            if not request:
                return {
                    "success": False,
                    "error": "Request not found"
                }
            
            # Get agent status
            agent_status = await self.crew.get_agent_status()
            
            return {
                "success": True,
                "request_id": request_id,
                "status": request.status,
                "created_at": request.created_at.isoformat(),
                "updated_at": request.updated_at.isoformat(),
                "agent_status": agent_status,
                "estimated_cost": request.estimated_cost,
                "scheduled_time": request.scheduled_time.isoformat() if request.scheduled_time else None,
                "assigned_contractor": request.assigned_contractor
            }
            
        except Exception as e:
            logger.error(f"Error getting request status: {str(e)}")
            return {
                "success": False,
                "error": "Failed to get status",
                "details": str(e)
            }

    async def cancel_request(self, request_id: str) -> Dict[str, Any]:
        """
        Cancel an active maintenance request if possible.
        
        Args:
            request_id: ID of the request to cancel
            
        Returns:
            Dictionary indicating success or failure
        """
        try:
            request = self.active_requests.get(request_id)
            if not request:
                return {
                    "success": False,
                    "error": "Request not found"
                }
            
            # Check if request can be cancelled
            if request.status in [RequestStatus.SCHEDULED, RequestStatus.COMPLETED]:
                return {
                    "success": False,
                    "error": "Cannot cancel request in current status"
                }
            
            # Update request status
            request.status = RequestStatus.FAILED
            request.updated_at = datetime.utcnow()
            
            logger.info(f"Request {request_id} cancelled successfully")
            return {
                "success": True,
                "request_id": request_id,
                "status": "cancelled"
            }
            
        except Exception as e:
            logger.error(f"Error cancelling request: {str(e)}")
            return {
                "success": False,
                "error": "Failed to cancel request",
                "details": str(e)
            }

    def get_active_requests(self) -> Dict[str, Any]:
        """Get summary of all active maintenance requests"""
        try:
            return {
                "success": True,
                "requests": [
                    {
                        "request_id": req_id,
                        "status": request.status,
                        "created_at": request.created_at.isoformat(),
                        "property_id": request.property_id
                    }
                    for req_id, request in self.active_requests.items()
                ]
            }
        except Exception as e:
            logger.error(f"Error getting active requests: {str(e)}")
            return {
                "success": False,
                "error": "Failed to get active requests",
                "details": str(e)
            }

    async def cleanup(self) -> None:
        """Cleanup resources and close connections"""
        try:
            # Cleanup logic here
            self.active_requests.clear()
            logger.info("Maintenance agent cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
            raise

# Global agent instance
_agent: Optional[MaintenanceAgent] = None

async def get_agent() -> MaintenanceAgent:
    """Get or create the global maintenance agent instance"""
    global _agent
    if _agent is None:
        _agent = MaintenanceAgent()
    return _agent