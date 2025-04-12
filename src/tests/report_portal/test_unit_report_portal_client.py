import pytest
from unittest.mock import patch, MagicMock
import requests

from src.alita_tools.report_portal.report_portal_client import RPClient

@pytest.fixture
def rp_client():
    """Create a RPClient instance for testing."""
    return RPClient(
        endpoint="https://reportportal.example.com/",  # With trailing slash
        api_key="mock_api_key",
        project="mock_project"
    )

@pytest.fixture
def mock_response():
    """Create a mock response."""
    response = MagicMock()
    response.json.return_value = {"key": "value"}
    return response

@pytest.mark.unit
@pytest.mark.report_portal
class TestReportPortalClient:
    """Unit tests for RPClient."""

    def test_init_strips_trailing_slash(self):
        """Test that endpoint trailing slash is stripped."""
        client = RPClient(
            endpoint="https://reportportal.example.com/",
            api_key="mock_api_key",
            project="mock_project"
        )
        assert client.endpoint == "https://reportportal.example.com"

    def test_init_without_trailing_slash(self):
        """Test initialization without trailing slash."""
        client = RPClient(
            endpoint="https://reportportal.example.com",
            api_key="mock_api_key",
            project="mock_project"
        )
        assert client.endpoint == "https://reportportal.example.com"

    def test_headers_creation(self, rp_client):
        """Test that headers are created correctly."""
        expected_headers = {
            "Accept": "application/json",
            "Authorization": "Bearer mock_api_key"
        }
        assert rp_client.headers == expected_headers

    @patch('requests.request')
    def test_export_specified_launch(self, mock_request, rp_client, mock_response):
        """Test export_specified_launch method."""
        mock_request.return_value = mock_response
        launch_id = "123"
        export_format = "html"

        response = rp_client.export_specified_launch(launch_id, export_format)

        expected_url = f"{rp_client.endpoint}/api/v1/{rp_client.project}/launch/{launch_id}/report?view={export_format}"
        mock_request.assert_called_once_with(
            "GET",
            expected_url,
            headers=rp_client.headers
        )
        assert response == mock_response

    @patch('requests.request')
    def test_get_launch_details(self, mock_request, rp_client, mock_response):
        """Test get_launch_details method."""
        mock_request.return_value = mock_response
        launch_id = "123"

        response = rp_client.get_launch_details(launch_id)

        expected_url = f"{rp_client.endpoint}/api/v1/{rp_client.project}/launch/{launch_id}"
        mock_request.assert_called_once_with(
            "GET",
            expected_url,
            headers=rp_client.headers
        )
        assert response == {"key": "value"}

    @patch('requests.request')
    def test_get_all_launches(self, mock_request, rp_client, mock_response):
        """Test get_all_launches method."""
        mock_request.return_value = mock_response
        page_number = 2

        response = rp_client.get_all_launches(page_number)

        expected_url = f"{rp_client.endpoint}/api/v1/{rp_client.project}/launch?page.page={page_number}"
        mock_request.assert_called_once_with(
            "GET",
            expected_url,
            headers=rp_client.headers
        )
        assert response == {"key": "value"}

    @patch('requests.request')
    def test_find_test_item_by_id(self, mock_request, rp_client, mock_response):
        """Test find_test_item_by_id method."""
        mock_request.return_value = mock_response
        item_id = "123"

        response = rp_client.find_test_item_by_id(item_id)

        expected_url = f"{rp_client.endpoint}/api/v1/{rp_client.project}/item/{item_id}"
        mock_request.assert_called_once_with(
            "GET",
            expected_url,
            headers=rp_client.headers
        )
        assert response == {"key": "value"}

    @patch('requests.request')
    def test_get_test_items_for_launch(self, mock_request, rp_client, mock_response):
        """Test get_test_items_for_launch method."""
        mock_request.return_value = mock_response
        launch_id = "123"
        page_number = 2

        response = rp_client.get_test_items_for_launch(launch_id, page_number)

        expected_url = f"{rp_client.endpoint}/api/v1/{rp_client.project}/item?filter.eq.launchId={launch_id}&page.page={page_number}"
        mock_request.assert_called_once_with(
            "GET",
            expected_url,
            headers=rp_client.headers
        )
        assert response == {"key": "value"}

    @patch('requests.request')
    def test_get_logs_for_test_items(self, mock_request, rp_client, mock_response):
        """Test get_logs_for_test_items method."""
        mock_request.return_value = mock_response
        item_id = "123"
        page_number = 2

        response = rp_client.get_logs_for_test_items(item_id, page_number)

        expected_url = f"{rp_client.endpoint}/api/v1/{rp_client.project}/log?filter.eq.item={item_id}&page.page={page_number}"
        mock_request.assert_called_once_with(
            "GET",
            expected_url,
            headers=rp_client.headers
        )
        assert response == {"key": "value"}

    @patch('requests.request')
    def test_get_user_information(self, mock_request, rp_client, mock_response):
        """Test get_user_information method."""
        mock_request.return_value = mock_response
        username = "testuser"

        response = rp_client.get_user_information(username)

        expected_url = f"{rp_client.endpoint}/api/users/{username}"
        mock_request.assert_called_once_with(
            "GET",
            expected_url,
            headers=rp_client.headers
        )
        assert response == {"key": "value"}

    @patch('requests.request')
    def test_get_dashboard_data(self, mock_request, rp_client, mock_response):
        """Test get_dashboard_data method."""
        mock_request.return_value = mock_response
        dashboard_id = "123"

        response = rp_client.get_dashboard_data(dashboard_id)

        expected_url = f"{rp_client.endpoint}/api/v1/{rp_client.project}/dashboard/{dashboard_id}"
        mock_request.assert_called_once_with(
            "GET",
            expected_url,
            headers=rp_client.headers
        )
        assert response == {"key": "value"}

    @patch('requests.request')
    def test_request_error_handling(self, mock_request, rp_client):
        """Test error handling in requests."""
        mock_request.side_effect = requests.exceptions.RequestException("API Error")
        
        with pytest.raises(requests.exceptions.RequestException, match="API Error"):
            rp_client.get_launch_details("123")
