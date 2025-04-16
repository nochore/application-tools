import json
from unittest.mock import MagicMock, patch, call
import pytest
import requests
import pymupdf # Added import
from src.alita_tools.report_portal.api_wrapper import ReportPortalApiWrapper
from src.alita_tools.report_portal.report_portal_client import RPClient

@pytest.fixture
def mock_rp_client():
    """Fixture to mock RPClient."""
    with patch('src.alita_tools.report_portal.api_wrapper.RPClient') as mock_client:
        yield mock_client

@pytest.fixture
def mock_response():
    """Fixture to create a mock response."""
    response = MagicMock()
    response.headers = {'Content-Disposition': 'attachment', 'Content-Type': 'text/html'}
    response.content = b'Test content'
    response.json.return_value = {'key': 'value'}
    return response

@pytest.fixture
def rp_wrapper(mock_rp_client):
    """Fixture to create a ReportPortalApiWrapper instance with mocks."""
    wrapper = ReportPortalApiWrapper(
        endpoint="https://reportportal.example.com",
        api_key="mock_api_key",
        project="mock_project"
    )
    return wrapper

@pytest.mark.unit
@pytest.mark.report_portal
class TestReportPortalWrapper:
    """Unit tests for ReportPortalApiWrapper."""

    @pytest.mark.positive
    def test_validate_toolkit_success(self, rp_wrapper):
        """Test successful validation of toolkit configuration."""
        values = {
            "endpoint": "https://reportportal.example.com",
            "api_key": "mock_api_key",
            "project": "mock_project"
        }
        result = rp_wrapper.validate_toolkit(values)
        assert result == values

    @pytest.mark.positive
    def test_get_available_tools(self, rp_wrapper):
        """Test retrieving the list of available tools."""
        tools = rp_wrapper.get_available_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        
        expected_tools = [
            "get_extended_launch_data_as_raw",
            "get_extended_launch_data",
            "get_launch_details",
            "get_all_launches",
            "find_test_item_by_id",
            "get_test_items_for_launch",
            "get_logs_for_test_items",
            "get_user_information",
            "get_dashboard_data"
        ]
        
        found_tools = [tool["name"] for tool in tools]
        for tool_name in expected_tools:
            assert tool_name in found_tools
            tool = next(t for t in tools if t["name"] == tool_name)
            assert callable(tool["ref"])
            assert tool["args_schema"] is not None

    @pytest.mark.positive
    def test_get_extended_launch_data_as_raw_success(self, rp_wrapper, mock_response):
        """Test getting extended launch data as raw successfully."""
        launch_id = "123"
        rp_wrapper._client.export_specified_launch.return_value = mock_response
        
        result = rp_wrapper.get_extended_launch_data_as_raw(launch_id)
        
        assert result == mock_response.content
        rp_wrapper._client.export_specified_launch.assert_called_once_with(launch_id, 'html')

    @pytest.mark.negative
    def test_get_extended_launch_data_as_raw_empty_response(self, rp_wrapper, mock_response):
        """Test getting extended launch data as raw with empty response."""
        launch_id = "123"
        mock_response.headers['Content-Disposition'] = ''
        rp_wrapper._client.export_specified_launch.return_value = mock_response
        
        result = rp_wrapper.get_extended_launch_data_as_raw(launch_id)
        
        assert result is None
        rp_wrapper._client.export_specified_launch.assert_called_once_with(launch_id, 'html')

    @pytest.mark.positive
    @patch('src.alita_tools.report_portal.api_wrapper.pymupdf.open')
    def test_get_extended_launch_data_html_success(self, mock_pymupdf_open, rp_wrapper, mock_response):
        """Test getting extended launch data with HTML content successfully."""
        launch_id = "123"
        mock_response.headers['Content-Type'] = 'text/html'
        rp_wrapper._client.export_specified_launch.return_value = mock_response

        # Mock pymupdf behavior
        mock_doc = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Page 1 text "
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "Page 2 text"
        mock_doc.__len__.return_value = 2
        mock_doc.__getitem__.side_effect = [mock_page1, mock_page2]
        mock_pymupdf_open.return_value.__enter__.return_value = mock_doc

        result = rp_wrapper.get_extended_launch_data(launch_id)

        assert result == "Page 1 text Page 2 text"
        rp_wrapper._client.export_specified_launch.assert_called_once_with(launch_id, 'html')
        mock_pymupdf_open.assert_called_once_with(stream=mock_response.content, filetype='html')
        assert mock_doc.__getitem__.call_count == 2
        mock_page1.get_text.assert_called_once()
        mock_page2.get_text.assert_called_once()

    @pytest.mark.positive
    @patch('src.alita_tools.report_portal.api_wrapper.pymupdf.open')
    def test_get_extended_launch_data_pdf_success(self, mock_pymupdf_open, rp_wrapper, mock_response):
        """Test getting extended launch data with PDF content successfully."""
        launch_id = "123"
        mock_response.headers['Content-Type'] = 'application/pdf'
        # Simulate calling with pdf format, although default is html, the code uses 'html' internally
        # This test ensures the pdf content type is handled correctly by pymupdf branch
        rp_wrapper._client.export_specified_launch.return_value = mock_response

        # Mock pymupdf behavior
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "PDF text content"
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page
        mock_pymupdf_open.return_value.__enter__.return_value = mock_doc

        result = rp_wrapper.get_extended_launch_data(launch_id)

        assert result == "PDF text content"
        # Note: The internal format variable is hardcoded to 'html' in the tested function
        rp_wrapper._client.export_specified_launch.assert_called_once_with(launch_id, 'html')
        mock_pymupdf_open.assert_called_once_with(stream=mock_response.content, filetype='html')
        mock_doc.__getitem__.assert_called_once_with(0)
        mock_page.get_text.assert_called_once()


    @pytest.mark.positive
    def test_get_launch_details_success(self, rp_wrapper, mock_response):
        """Test getting launch details successfully."""
        launch_id = "123"
        expected_result = {'key': 'value'}
        rp_wrapper._client.get_launch_details.return_value = expected_result
        
        result = rp_wrapper.get_launch_details(launch_id)
        
        assert result == expected_result
        rp_wrapper._client.get_launch_details.assert_called_once_with(launch_id)

    @pytest.mark.positive
    def test_get_all_launches_success(self, rp_wrapper, mock_response):
        """Test getting all launches successfully."""
        page_number = 1
        expected_result = {'key': 'value'}
        rp_wrapper._client.get_all_launches.return_value = expected_result
        
        result = rp_wrapper.get_all_launches(page_number)
        
        assert result == expected_result
        rp_wrapper._client.get_all_launches.assert_called_once_with(page_number)

    @pytest.mark.positive
    def test_find_test_item_by_id_success(self, rp_wrapper, mock_response):
        """Test finding test item by ID successfully."""
        item_id = "123"
        expected_result = {'key': 'value'}
        rp_wrapper._client.find_test_item_by_id.return_value = expected_result
        
        result = rp_wrapper.find_test_item_by_id(item_id)
        
        assert result == expected_result
        rp_wrapper._client.find_test_item_by_id.assert_called_once_with(item_id)

    @pytest.mark.positive
    def test_get_test_items_for_launch_success(self, rp_wrapper, mock_response):
        """Test getting test items for launch successfully."""
        launch_id = "123"
        page_number = 1
        expected_result = {'key': 'value'}
        rp_wrapper._client.get_test_items_for_launch.return_value = expected_result
        
        result = rp_wrapper.get_test_items_for_launch(launch_id, page_number)
        
        assert result == expected_result
        rp_wrapper._client.get_test_items_for_launch.assert_called_once_with(launch_id, page_number)

    @pytest.mark.positive
    def test_get_logs_for_test_items_success(self, rp_wrapper, mock_response):
        """Test getting logs for test items successfully."""
        item_id = "123"
        page_number = 1
        expected_result = {'key': 'value'}
        rp_wrapper._client.get_logs_for_test_items.return_value = expected_result
        
        result = rp_wrapper.get_logs_for_test_items(item_id, page_number)
        
        assert result == expected_result
        rp_wrapper._client.get_logs_for_test_items.assert_called_once_with(item_id, page_number)

    @pytest.mark.positive
    def test_get_user_information_success(self, rp_wrapper, mock_response):
        """Test getting user information successfully."""
        username = "testuser"
        expected_result = {'key': 'value'}
        rp_wrapper._client.get_user_information.return_value = expected_result
        
        result = rp_wrapper.get_user_information(username)
        
        assert result == expected_result
        rp_wrapper._client.get_user_information.assert_called_once_with(username)

    @pytest.mark.positive
    def test_get_dashboard_data_success(self, rp_wrapper, mock_response):
        """Test getting dashboard data successfully."""
        dashboard_id = "123"
        expected_result = {'key': 'value'}
        rp_wrapper._client.get_dashboard_data.return_value = expected_result
        
        result = rp_wrapper.get_dashboard_data(dashboard_id)
        
        assert result == expected_result
        rp_wrapper._client.get_dashboard_data.assert_called_once_with(dashboard_id)

    @pytest.mark.negative
    def test_get_extended_launch_data_unsupported_format(self, rp_wrapper, mock_response):
        """Test getting extended launch data with unsupported format."""
        launch_id = "123"
        mock_response.headers['Content-Type'] = 'application/unsupported'
        rp_wrapper._client.export_specified_launch.return_value = mock_response
        
        result = rp_wrapper.get_extended_launch_data(launch_id)
        
        assert result is None

    @pytest.mark.negative
    def test_get_extended_launch_data_empty_response(self, rp_wrapper, mock_response):
        """Test getting extended launch data with empty response."""
        launch_id = "123"
        mock_response.headers['Content-Disposition'] = ''
        rp_wrapper._client.export_specified_launch.return_value = mock_response
        
        result = rp_wrapper.get_extended_launch_data(launch_id)
        
        assert result is None

    @pytest.mark.negative
    def test_get_extended_launch_data_api_error(self, rp_wrapper, mock_response):
        """Test getting extended launch data when API call fails."""
        launch_id = "123"
        rp_wrapper._client.export_specified_launch.side_effect = requests.exceptions.RequestException("API Error")
        
        result = rp_wrapper.get_extended_launch_data(launch_id)
        
        assert result is None

    @pytest.mark.negative
    def test_get_launch_details_api_error(self, rp_wrapper):
        """Test getting launch details when API call fails."""
        launch_id = "123"
        rp_wrapper._client.get_launch_details.side_effect = requests.exceptions.RequestException("API Error")
        
        result = rp_wrapper.get_launch_details(launch_id)
        
        assert result == {"error": "API Error"}

    @pytest.mark.negative
    def test_get_all_launches_api_error(self, rp_wrapper):
        """Test getting all launches when API call fails."""
        page_number = 1
        rp_wrapper._client.get_all_launches.side_effect = requests.exceptions.RequestException("API Error")
        
        result = rp_wrapper.get_all_launches(page_number)
        
        assert result == {"error": "API Error"}

    @pytest.mark.negative
    def test_find_test_item_by_id_api_error(self, rp_wrapper):
        """Test finding test item by ID when API call fails."""
        item_id = "123"
        rp_wrapper._client.find_test_item_by_id.side_effect = requests.exceptions.RequestException("API Error")
        
        result = rp_wrapper.find_test_item_by_id(item_id)
        
        assert result == {"error": "API Error"}

    @pytest.mark.negative
    def test_get_test_items_for_launch_api_error(self, rp_wrapper):
        """Test getting test items for launch when API call fails."""
        launch_id = "123"
        page_number = 1
        rp_wrapper._client.get_test_items_for_launch.side_effect = requests.exceptions.RequestException("API Error")
        
        result = rp_wrapper.get_test_items_for_launch(launch_id, page_number)
        
        assert result == {"error": "API Error"}

    @pytest.mark.negative
    def test_get_logs_for_test_items_api_error(self, rp_wrapper):
        """Test getting logs for test items when API call fails."""
        item_id = "123"
        page_number = 1
        rp_wrapper._client.get_logs_for_test_items.side_effect = requests.exceptions.RequestException("API Error")
        
        result = rp_wrapper.get_logs_for_test_items(item_id, page_number)
        
        assert result == {"error": "API Error"}

    @pytest.mark.negative
    def test_get_user_information_api_error(self, rp_wrapper):
        """Test getting user information when API call fails."""
        username = "testuser"
        rp_wrapper._client.get_user_information.side_effect = requests.exceptions.RequestException("API Error")
        
        result = rp_wrapper.get_user_information(username)
        
        assert result == {"error": "API Error"}

    @pytest.mark.negative
    def test_get_dashboard_data_api_error(self, rp_wrapper):
        """Test getting dashboard data when API call fails."""
        dashboard_id = "123"
        rp_wrapper._client.get_dashboard_data.side_effect = requests.exceptions.RequestException("API Error")
        
        result = rp_wrapper.get_dashboard_data(dashboard_id)
        
        assert result == {"error": "API Error"}
