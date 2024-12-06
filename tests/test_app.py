import pytest
from unittest.mock import AsyncMock, Mock, patch
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import uuid
from typing import Dict, Any

from app.streamlit_app import DomiInterface
from app.database import Database
from app.s3 import S3Handler
from agent.crew import DomiCrew

# Test data
SAMPLE_PROPERTY = {
    "id": str(uuid.uuid4()),
    "name": "Test Property",
    "address": "123 Test Street",
    "units": 10,
    "status": "active",
    "created_at": datetime.now(timezone.utc)
}

SAMPLE_REQUEST = {
    "property_id": SAMPLE_PROPERTY["id"],
    "description": "Water leak in kitchen",
    "contact_email": "tenant@example.com",
    "contact_phone": "+1234567890",
    "priority": "high",
    "photos": []
}

@pytest.fixture
def mock_streamlit():
    """Mock Streamlit components"""
    with patch("streamlit.set_page_config"), \
         patch("streamlit.sidebar.title"), \
         patch("streamlit.sidebar.radio"), \
         patch("streamlit.header"), \
         patch("streamlit.form") as mock_form:
        
        # Mock form components
        mock_form.return_value.__enter__.return_value = Mock()
        mock_form.return_value.__exit__.return_value = None
        
        yield mock_form

@pytest.fixture
async def app_interface(test_settings, populated_test_db, mock_streamlit):
    """Initialize application interface with test dependencies"""
    interface = DomiInterface()
    interface.db = populated_test_db
    interface.settings = test_settings
    return interface

@pytest.mark.asyncio
class TestDomiInterface:
    """Test suite for Streamlit interface"""

    async def test_initialization(self, app_interface):
        """Test interface initialization"""
        assert app_interface.settings is not None
        assert app_interface.db is not None
        assert app_interface.s3 is not None
        assert app_interface.crew is not None
        assert 'authenticated' in st.session_state
        assert 'user_role' in st.session_state

    async def test_load_properties(self, app_interface):
        """Test property data loading"""
        properties = await app_interface.load_properties()
        assert isinstance(properties, pd.DataFrame)
        assert not properties.empty
        assert 'id' in properties.columns
        assert 'name' in properties.columns
        assert 'address' in properties.columns

    async def test_load_maintenance_requests(self, app_interface):
        """Test maintenance request loading"""
        # Test without property filter
        all_requests = await app_interface.load_maintenance_requests()
        assert isinstance(all_requests, pd.DataFrame)
        assert 'property_name' in all_requests.columns
        
        # Test with property filter
        filtered_requests = await app_interface.load_maintenance_requests(SAMPLE_PROPERTY["id"])
        assert all(req['property_id'] == SAMPLE_PROPERTY["id"] for _, req in filtered_requests.iterrows())

    @pytest.mark.parametrize("page", ["Dashboard", "Submit Request", "Properties"])
    async def test_page_navigation(self, app_interface, page, mock_streamlit):
        """Test page navigation"""
        with patch("streamlit.sidebar.radio", return_value=page):
            await app_interface.main()
            if page == "Dashboard":
                mock_streamlit.assert_called()

    async def test_maintenance_form_submission(self, app_interface, mock_streamlit):
        """Test maintenance request form submission"""
        with patch("streamlit.form") as mock_form:
            # Mock form inputs
            mock_form.return_value.__enter__.return_value.selectbox.return_value = SAMPLE_REQUEST["property_id"]
            mock_form.return_value.__enter__.return_value.text_area.return_value = SAMPLE_REQUEST["description"]
            mock_form.return_value.__enter__.return_value.text_input.side_effect = [
                SAMPLE_REQUEST["contact_email"],
                SAMPLE_REQUEST["contact_phone"]
            ]
            mock_form.return_value.__enter__.return_value.file_uploader.return_value = []
            mock_form.return_value.__enter__.return_value.form_submit_button.return_value = True
            
            await app_interface.render_maintenance_form()
            
            # Verify form was processed
            mock_form.assert_called_once()

    @patch("streamlit.dataframe")
    @patch("streamlit.columns")
    async def test_dashboard_rendering(self, mock_columns, mock_dataframe, app_interface):
        """Test dashboard rendering"""
        # Mock filter selections
        mock_columns.return_value[0].selectbox.return_value = "All"
        mock_columns.return_value[1].multiselect.return_value = ["new", "in_progress"]
        
        await app_interface.render_dashboard()
        
        # Verify dashboard components were rendered
        mock_dataframe.assert_called_once()

    async def test_request_creation(self, app_interface):
        """Test maintenance request creation flow"""
        result = await app_interface.create_maintenance_request(
            SAMPLE_REQUEST,
            photo_urls=["test_photo.jpg"]
        )
        
        # Verify request was created
        assert result is not None
        
        # Verify in database
        request = await app_interface.db.fetch_one(
            "SELECT * FROM maintenance_requests WHERE property_id = $1",
            SAMPLE_REQUEST["property_id"]
        )
        assert request is not None
        assert request["description"] == SAMPLE_REQUEST["description"]

    async def test_error_handling(self, app_interface):
        """Test error handling in interface"""
        # Test invalid property ID
        with pytest.raises(Exception):
            await app_interface.create_maintenance_request({
                **SAMPLE_REQUEST,
                "property_id": "invalid-id"
            })
        
        # Test invalid file upload
        with patch("streamlit.form") as mock_form:
            mock_form.return_value.__enter__.return_value.file_uploader.return_value = [
                Mock(type="invalid/type")
            ]
            await app_interface.render_maintenance_form()
            mock_form.return_value.__enter__.return_value.error.assert_called_once()

    @patch("streamlit.success")
    @patch("streamlit.error")
    async def test_notification_display(self, mock_error, mock_success, app_interface):
        """Test notification display"""
        # Test success notification
        await app_interface.create_maintenance_request(SAMPLE_REQUEST)
        mock_success.assert_called_once()
        
        # Test error notification
        with pytest.raises(Exception):
            await app_interface.create_maintenance_request({})
        mock_error.assert_called_once()

class TestIntegration:
    """Integration tests for complete UI flow"""

    @pytest.fixture
    async def setup_test_env(self, app_interface, populated_test_db):
        """Set up test environment"""
        return app_interface, populated_test_db

    @pytest.mark.asyncio
    async def test_complete_request_flow(self, setup_test_env, mock_streamlit):
        """Test complete maintenance request flow through UI"""
        interface, db = setup_test_env
        
        # Submit request through form
        with patch("streamlit.form") as mock_form:
            mock_form.return_value.__enter__.return_value.selectbox.return_value = SAMPLE_REQUEST["property_id"]
            mock_form.return_value.__enter__.return_value.text_area.return_value = SAMPLE_REQUEST["description"]
            mock_form.return_value.__enter__.return_value.text_input.side_effect = [
                SAMPLE_REQUEST["contact_email"],
                SAMPLE_REQUEST["contact_phone"]
            ]
            mock_form.return_value.__enter__.return_value.form_submit_button.return_value = True
            
            await interface.render_maintenance_form()
        
        # Verify request in database
        requests = await db.fetch_all(
            "SELECT * FROM maintenance_requests WHERE property_id = $1",
            SAMPLE_REQUEST["property_id"]
        )
        assert len(requests) > 0
        
        # Verify dashboard update
        with patch("streamlit.dataframe") as mock_dataframe:
            await interface.render_dashboard()
            mock_dataframe.assert_called_once()

if __name__ == "__main__":
    pytest.main(["-v", "test_app.py"])