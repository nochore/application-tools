import json
import logging
import requests
from unittest.mock import MagicMock, patch

import pytest
from FigmaPy import FigmaPy
from langchain_core.tools import ToolException

from src.alita_tools.figma.api_wrapper import FigmaApiWrapper

@pytest.fixture
def mock_figmapy():
    """Fixture to mock FigmaPy client."""
    with patch('src.alita_tools.figma.api_wrapper.FigmaPy') as mock_client:
        yield mock_client

@pytest.fixture
def mock_requests():
    """Fixture to mock requests."""
    with patch('src.alita_tools.figma.api_wrapper.requests') as mock_req:
        yield mock_req

@pytest.fixture
def figma_wrapper(mock_figmapy, mock_requests):
    """Fixture to create a FigmaApiWrapper instance with mocks."""
    wrapper = FigmaApiWrapper(
        token="mock_token",
        global_limit=1000,
        global_regexp=None
    )
    return wrapper

@pytest.mark.unit
@pytest.mark.figma
class TestFigmaApiWrapper:
    
    @pytest.mark.positive
    def test_validate_toolkit_success(self, mock_figmapy):
        """Test successful validation of toolkit with token."""
        mock_figmapy.return_value = MagicMock()
        wrapper = FigmaApiWrapper(
            token="mock_token",
            global_limit=1000,
            global_regexp=None,
            oauth2=None
        )
        assert isinstance(wrapper._client, MagicMock)
        mock_figmapy.assert_called_once_with(token="mock_token", oauth2=False)

    @pytest.mark.positive
    def test_validate_toolkit_with_oauth2(self, mock_figmapy):
        """Test successful validation of toolkit with OAuth2."""
        mock_figmapy.return_value = MagicMock()
        wrapper = FigmaApiWrapper(
            token=None,
            oauth2="mock_oauth2_token",
            global_limit=1000,
            global_regexp=None
        )
        assert isinstance(wrapper._client, MagicMock)
        mock_figmapy.assert_called_once_with(token="mock_oauth2_token", oauth2=True)

    @pytest.mark.negative
    def test_validate_toolkit_no_auth(self):
        """Test validation fails when no authentication is provided."""
        with pytest.raises(ToolException, match="You have to define Figma token"):
            FigmaApiWrapper(
                token=None,
                oauth2=None,
                global_limit=1000,
                global_regexp=None
            ).validate_toolkit()

    @pytest.mark.negative
    def test_validate_toolkit_invalid_regexp(self):
        """Test validation fails with invalid regex pattern."""
        with pytest.raises(ToolException, match="Failed to compile regex pattern"):
            FigmaApiWrapper(
                token="mock_token",
                global_regexp="[invalid",  # Invalid regex pattern
                global_limit=1000,
                oauth2=None
            ).validate_toolkit()

    @pytest.mark.positive
    def test_send_request_success(self, figma_wrapper, mock_requests):
        """Test successful HTTP request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}
        mock_requests.request.return_value = mock_response

        result = figma_wrapper._send_request(
            method="GET",
            url="https://api.figma.com/v1/test",
            payload={"test": "data"},
            extra_headers={"X-Custom": "test"}
        )

        assert result == mock_response
        mock_requests.request.assert_called_once_with(
            "GET",
            "https://api.figma.com/v1/test",
            headers={
                "Content-Type": "application/json",
                "X-Figma-Token": "mock_token",
                "X-Custom": "test"
            },
            json={"test": "data"}
        )

    @pytest.mark.negative
    def test_send_request_error(self, figma_wrapper, mock_requests):
        """Test HTTP request failure."""
        mock_requests.request.side_effect = requests.exceptions.RequestException("Network error")

        with pytest.raises(ToolException, match="HTTP request failed: Network error"):
            figma_wrapper._send_request(
                method="GET",
                url="https://api.figma.com/v1/test"
            )

    @pytest.mark.positive
    def test_get_file_nodes_success(self, figma_wrapper):
        """Test successful file nodes retrieval."""
        mock_response = {"nodes": {"123": {"document": {"name": "Test"}}}}
        figma_wrapper._client.api_request.return_value = mock_response

        result = figma_wrapper.get_file_nodes(
            file_key="abc123",
            ids="123,456"
        )

        figma_wrapper._client.api_request.assert_called_once_with(
            "files/abc123/nodes?ids=123,456",
            method="get"
        )
        result_dict = json.loads(result)
        assert result_dict["nodes"]["123"]["document"]["name"] == "Test"

    @pytest.mark.positive
    def test_get_file_success(self, figma_wrapper):
        """Test successful file retrieval."""
        mock_response = {"document": {"name": "Test File"}}
        figma_wrapper._client.get_file.return_value = mock_response

        result = figma_wrapper.get_file(
            file_key="abc123",
            geometry="paths",
            version="123"
        )

        figma_wrapper._client.get_file.assert_called_once_with(
            "abc123",
            "paths",
            "123"
        )
        assert json.loads(result)["document"]["name"] == "Test File"

    @pytest.mark.positive
    def test_get_available_tools(self, figma_wrapper):
        """Test getting available tools."""
        tools = figma_wrapper.get_available_tools()
        
        assert isinstance(tools, list)
        assert len(tools) == 8  # Number of available tools
        
        # Check first tool structure
        first_tool = tools[0]
        assert "name" in first_tool
        assert "description" in first_tool
        assert "args_schema" in first_tool
        assert "ref" in first_tool
        assert first_tool["name"] == "get_file_nodes"

    @pytest.mark.positive
    def test_process_output_decorator(self, figma_wrapper):
        """Test process_output decorator functionality."""
        test_data = {"test": "data", "nested": {"value": 123}}
        
        @FigmaApiWrapper.process_output
        def mock_api_call(self, *args, **kwargs):
            return test_data

        result = mock_api_call(figma_wrapper)
        parsed_result = json.loads(result)
        assert parsed_result["test"] == "data"
        assert parsed_result["nested"]["value"] == 123

    @pytest.mark.negative
    def test_process_output_with_error(self, figma_wrapper):
        """Test process_output decorator with error handling."""
        @FigmaApiWrapper.process_output
        def mock_failing_call(self, *args, **kwargs):
            raise ValueError("Test error")

        result = mock_failing_call(figma_wrapper)
        assert isinstance(result, ToolException)
        assert "Error in 'mock_failing_call': Test error" in str(result)
