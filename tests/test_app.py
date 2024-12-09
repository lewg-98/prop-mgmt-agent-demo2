import pytest
from unittest.mock import patch
import streamlit as st
from datetime import datetime
from app.streamlit_app import DomiInterface

@pytest.fixture
def mock_streamlit():
    """Mock Streamlit components"""
    with patch("streamlit.set_page_config"), \
         patch("streamlit.title"), \
         patch("streamlit.form") as mock_form:
        mock_form.return_value.__enter__.return_value = mock_form
        mock_form.return_value.__exit__.return_value = None
        yield mock_form

@pytest.fixture
async def app_interface(test_settings, populated_db):
    interface = DomiInterface()
    interface.db = populated_db
    interface.settings = test_settings
    return interface

@pytest.mark.asyncio
class TestDomiInterface:
    async def test_maintenance_form(self, app_interface, mock_streamlit, sample_data):
        """Test maintenance request submission"""
        with patch("streamlit.form") as mock_form:
            mock_form.return_value.__enter__.return_value.selectbox.return_value = sample_data['property']['id']
            mock_form.return_value.__enter__.return_value.text_area.return_value = "Water leak"
            mock_form.return_value.__enter__.return_value.text_input.side_effect = ["test@example.com", "123-456-7890"]
            mock_form.return_value.__enter__.return_value.form_submit_button.return_value = True
            
            result = await app_interface.render_maintenance_form()
            assert result['success'] is True
            assert 'request_id' in result

    async def test_dashboard_rendering(self, app_interface, mock_streamlit, populated_db):
        """Test dashboard display"""
        requests = await populated_db.fetch_all("maintenance_requests")
        with patch("streamlit.dataframe") as mock_df:
            await app_interface.render_dashboard()
            mock_df.assert_called_once()
            displayed_data = mock_df.call_args[0][0]
            assert len(displayed_data) == len(requests)

    async def test_error_display(self, app_interface, mock_streamlit):
        """Test error handling display"""
        with patch("streamlit.error") as mock_error:
            await app_interface.create_maintenance_request({})
            mock_error.assert_called_once()

    async def test_status_updates(self, app_interface, mock_streamlit, sample_data):
        """Test request status updates"""
        with patch("streamlit.success") as mock_success:
            result = await app_interface.create_maintenance_request({
                'property_id': sample_data['property']['id'],
                'description': 'Test request',
                'contact_email': 'test@example.com'
            })
            assert result['success'] is True
            mock_success.assert_called_once()

            with patch("streamlit.status") as mock_status:
                updated = await app_interface.update_request_status(result['request_id'], 'processing')
                assert updated['status'] == 'processing'
                mock_status.assert_called_once()