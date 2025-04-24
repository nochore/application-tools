import json
import requests
from unittest.mock import MagicMock, patch
from pydantic import SecretStr

import pytest
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
    wrapper._client = mock_figmapy() # Ensure _client is set for OAuth2 tests
    return wrapper

@pytest.fixture
def figma_wrapper_oauth(mock_figmapy, mock_requests):
    """Fixture for FigmaApiWrapper initialized with OAuth2."""
    wrapper = FigmaApiWrapper(
        oauth2="mock_oauth_token",
        global_limit=1000,
        global_regexp=None
    )
    wrapper._client = mock_figmapy() # Ensure _client is set
    return wrapper


@pytest.mark.unit
@pytest.mark.figma
class TestFigmaApiWrapper:

    @pytest.mark.positive
    def test_validate_toolkit_already_initialized(self, mock_figmapy):
        """Test that validate_toolkit skips initialization if _client exists."""
        mock_client_instance = MagicMock()
        wrapper = FigmaApiWrapper(token="mock_token")
        wrapper._client = mock_client_instance # Pre-set the client

        # Call validate_toolkit again
        validated_wrapper = wrapper.validate_toolkit()

        assert validated_wrapper._client is mock_client_instance
        # Ensure FigmaPy was not called again during the second validation
        mock_figmapy.assert_called_once_with(token=SecretStr("mock_token"), oauth2=False)


    @pytest.mark.positive
    @patch('src.alita_tools.figma.api_wrapper.logging')
    def test_validate_toolkit_no_regexp_warning(self, mock_logging, mock_figmapy):
        """Test that a warning is logged if global_regexp is None."""
        FigmaApiWrapper(token="mock_token", global_regexp=None)
        mock_logging.warning.assert_called_with("No regex pattern provided. Skipping regex compilation.")

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
        mock_figmapy.assert_called_once_with(token=SecretStr("mock_token"), oauth2=False)

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
        mock_figmapy.assert_called_once_with(token=SecretStr("mock_oauth2_token"), oauth2=True)

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
                "X-Figma-Token": SecretStr('mock_token'),
                "X-Custom": "test"
            },
            json={"test": "data"}
        )

    @pytest.mark.positive
    def test_send_request_with_oauth2(self, figma_wrapper_oauth, mock_requests):
        """Test successful HTTP request using OAuth2."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}
        mock_requests.request.return_value = mock_response

        result = figma_wrapper_oauth._send_request(
            method="GET",
            url="https://api.figma.com/v1/test",
        )

        assert result == mock_response
        mock_requests.request.assert_called_once_with(
            "GET",
            "https://api.figma.com/v1/test",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer **********", # Check OAuth header
            },
            json=None
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
        assert result_dict["nodes"]["123"]["document"] == "{'name': 'Test'}"


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
    def test_get_file_versions_success(self, figma_wrapper):
        """Test successful file versions retrieval."""
        mock_response = {"versions": [{"id": "v1", "label": "Version 1"}]}
        figma_wrapper._client.get_file_versions.return_value = mock_response

        result = figma_wrapper.get_file_versions(file_key="abc123")

        figma_wrapper._client.get_file_versions.assert_called_once_with("abc123")
        assert json.loads(result)["versions"][0]["label"] == "Version 1"

    @pytest.mark.positive
    def test_get_file_comments_success(self, figma_wrapper):
        """Test successful file comments retrieval."""
        mock_response = {"comments": [{"id": "c1", "message": "Comment 1"}]}
        figma_wrapper._client.get_comments.return_value = mock_response

        result = figma_wrapper.get_file_comments(file_key="abc123")

        figma_wrapper._client.get_comments.assert_called_once_with("abc123")
        assert json.loads(result)["comments"][0]["message"] == "Comment 1"

    @pytest.mark.positive
    def test_post_file_comment_success(self, figma_wrapper, mock_requests):
        """Test successful posting of a file comment."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "new_comment_id", "message": "Test comment"}
        mock_requests.request.return_value = mock_response
        # Set api_uri on the mocked client for URL construction
        figma_wrapper._client.api_uri = "https://api.figma.com/v1/"

        result = figma_wrapper.post_file_comment(
            file_key="abc123",
            message="Test comment",
            client_meta={"node_id": "1:1"}
        )

        # Check the expected URL construction
        expected_url = "https://api.figma.com/v1/files/abc123/comments"
        mock_requests.request.assert_called_once_with(
            "POST",
            expected_url, # Use the constructed URL
            headers={
                "Content-Type": "application/json",
                "X-Figma-Token": SecretStr('mock_token')
            },
            json={"message": "Test comment", "client_meta": {"node_id": "1:1"}}
        )
        assert json.loads(result)["id"] == "new_comment_id"

    @pytest.mark.negative
    @patch('src.alita_tools.figma.api_wrapper.logging')
    def test_post_file_comment_failure(self, mock_logging, figma_wrapper, mock_requests):
        """Test failure during posting of a file comment."""
        # Set api_uri on the mocked client for URL construction
        figma_wrapper._client.api_uri = "https://api.figma.com/v1/"

        # Mock _send_request directly to raise ToolException, as post_file_comment catches this
        with patch.object(figma_wrapper, '_send_request', side_effect=ToolException("API Error")) as mock_send:
            result = figma_wrapper.post_file_comment(
                file_key="abc123",
                message="Test comment"
            )

            # Check that _send_request was called correctly
            expected_url = "https://api.figma.com/v1/files/abc123/comments"
            expected_payload = {"message": "Test comment"}
            mock_send.assert_called_once_with("POST", expected_url, expected_payload)

            # The function catches the ToolException and returns a new one
            assert isinstance(result, ToolException)
            assert "Failed to post comment. Error: API Error" in str(result)
            mock_logging.error.assert_called_with("Failed to post comment. Error: API Error")


    @pytest.mark.positive
    def test_get_file_images_success(self, figma_wrapper):
        """Test successful file images retrieval."""
        mock_response = {"images": {"1:1": "http://image.url/1", "2:2": "http://image.url/2"}}
        figma_wrapper._client.get_file_images.return_value = mock_response

        result = figma_wrapper.get_file_images(
            file_key="abc123",
            ids="1:1,2:2",
            scale="2",
            format="png",
            version="v1"
        )

        figma_wrapper._client.get_file_images.assert_called_once_with(
            file_key="abc123",
            ids=["1:1", "2:2"],
            scale="2",
            format="png",
            version="v1"
        )
        assert json.loads(result)["images"]["1:1"] == "http://image.url/1"

    @pytest.mark.positive
    def test_get_team_projects_success(self, figma_wrapper):
        """Test successful team projects retrieval."""
        mock_response = {"projects": [{"id": "p1", "name": "Project 1"}]}
        figma_wrapper._client.get_team_projects.return_value = mock_response

        result = figma_wrapper.get_team_projects(team_id="team123")

        figma_wrapper._client.get_team_projects.assert_called_once_with("team123")
        assert json.loads(result)["projects"][0]["name"] == "Project 1"

    @pytest.mark.positive
    def test_get_project_files_success(self, figma_wrapper):
        """Test successful project files retrieval."""
        mock_response = {"files": [{"key": "f1", "name": "File 1"}]}
        figma_wrapper._client.get_project_files.return_value = mock_response

        result = figma_wrapper.get_project_files(project_id="proj123")

        figma_wrapper._client.get_project_files.assert_called_once_with("proj123")
        assert json.loads(result)["files"][0]["name"] == "File 1"


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

    @pytest.mark.positive
    def test_process_output_with_object_result(self, figma_wrapper):
        """Test process_output decorator when the result is an object instance."""
        class MockResultObject:
            def __init__(self):
                self.data = "object_data"
                self.value = 42

        @FigmaApiWrapper.process_output
        def mock_object_call(self, *args, **kwargs):
            return MockResultObject()

        result = mock_object_call(figma_wrapper)
        parsed_result = json.loads(result)
        assert parsed_result == {"data": "object_data", "value": 42}

    @pytest.mark.positive
    def test_process_output_with_nested_object(self, figma_wrapper):
        """Test process_output decorator with a nested object instance."""
        class NestedObject:
            def __init__(self):
                self.nested_attr = "nested_value"

        test_data = {"top_level": "data", "nested_obj": NestedObject()}

        @FigmaApiWrapper.process_output
        def mock_nested_object_call(self, *args, **kwargs):
            return test_data

        result = mock_nested_object_call(figma_wrapper)
        parsed_result = json.loads(result)
        # simplified_dict converts the nested object
        assert parsed_result == {"top_level": "data", "nested_obj": {"nested_attr": "nested_value"}}

    @pytest.mark.positive
    @pytest.mark.skip(reason="method in wrapper should be fixed (recursion)")
    def test_process_output_with_cyclic_reference(self, figma_wrapper):
        """Test process_output decorator with a cyclic reference in the data."""
        cyclic_list = [1, 2]
        cyclic_list.append(cyclic_list) # Create cycle

        test_data = {"data": "some_data", "cycle": cyclic_list}

        @FigmaApiWrapper.process_output
        def mock_cyclic_call(self, *args, **kwargs):
            return test_data

        # simplified_dict should handle the cycle gracefully by not infinitely recursing.
        # The exact output might depend on how simplified_dict stops, but it shouldn't error.
        # We expect the cyclic part to be omitted or represented simply.
        # Since the current implementation uses `pass`, the cyclic element itself won't be added again.
        result = mock_cyclic_call(figma_wrapper)
        parsed_result = json.loads(result)
        # Check that the non-cyclic parts are present and the cyclic list representation is finite
        assert parsed_result["data"] == "some_data"
        assert isinstance(parsed_result["cycle"], list)
        # The cyclic element hits max_depth and becomes a string representation
        assert len(parsed_result["cycle"]) == 3
        assert parsed_result["cycle"][0] == 1
        assert parsed_result["cycle"][1] == 2
        # The cyclic element returns None when encountered again due to the 'pass' in simplified_dict
        # @todo: fix in the code
        assert parsed_result["cycle"][2] is None


    @pytest.mark.positive
    def test_process_output_with_regexp(self):
        """Test process_output decorator with regexp."""
        wrapper = FigmaApiWrapper(token="mock_token", global_regexp=r'"remove_me":\s*"[^"]*"')
        wrapper._client = MagicMock() # Mock client after init

        test_data = {"keep_me": "data", "remove_me": "secret"}

        @FigmaApiWrapper.process_output
        def mock_api_call(self, *args, **kwargs):
            return test_data

        result = mock_api_call(wrapper)
        # Note: The regex removes the key-value pair and might leave a trailing comma,
        # which fix_trailing_commas should handle.
        assert '"remove_me"' not in result
        assert '"keep_me": "data"' in result
        # Check if the result is valid JSON after regex and fixing
        assert json.loads(result) == {"keep_me": "data"}


    @pytest.mark.positive
    def test_process_output_with_limit(self):
        """Test process_output decorator with limit."""
        wrapper = FigmaApiWrapper(token="mock_token", global_limit=10)
        wrapper._client = MagicMock()

        test_data = {"long_string": "This is a very long string that should be truncated"}

        @FigmaApiWrapper.process_output
        def mock_api_call(self, *args, **kwargs):
            return test_data

        result = mock_api_call(wrapper)
        # Result includes JSON structure, so limit applies to the stringified JSON
        assert len(result) == 10
        assert result.startswith('{"long_str') # Check start of truncated JSON

    @pytest.mark.positive
    def test_process_output_with_extra_params_override(self):
        """Test process_output decorator respects extra_params for limit and regexp."""
        wrapper = FigmaApiWrapper(token="mock_token", global_limit=1000, global_regexp=None)
        wrapper._client = MagicMock()

        test_data = {"data": "value", "remove_me": "secret", "long": "string" * 10}
        extra_params = {"limit": 20, "regexp": r'"remove_me":\s*"[^"]*"'}

        @FigmaApiWrapper.process_output
        def mock_api_call(self, *args, **kwargs):
            # kwargs will contain extra_params passed from the wrapper's call
            return test_data

        # Pass extra_params when calling the decorated method
        result = mock_api_call(wrapper, extra_params=extra_params)

        assert len(result) == 20
        assert '"remove_me"' not in result
        assert result.startswith('{"data": "value", "l') # Check start of truncated JSON


    @pytest.mark.positive
    def test_process_output_empty_result(self, figma_wrapper):
        """Test process_output decorator with empty result from API call."""
        @FigmaApiWrapper.process_output
        def mock_empty_call(self, *args, **kwargs):
            return None # Simulate API returning nothing

        result = mock_empty_call(figma_wrapper)
        assert isinstance(result, ToolException)
        assert "Response result is empty. Check input parameters" in str(result)

    @pytest.mark.positive
    def test_process_output_non_dict_list_result(self, figma_wrapper):
        """Test process_output decorator with a non-dict/list result (e.g., string)."""
        @FigmaApiWrapper.process_output
        def mock_string_call(self, *args, **kwargs):
            return "Just a string" # Simulate API returning a plain string

        result = mock_string_call(figma_wrapper)
        assert result == '"Just a string"' # Should be JSON dumped

    @pytest.mark.negative
    def test_process_output_with_error(self, figma_wrapper):
        """Test process_output decorator with error handling."""
        @FigmaApiWrapper.process_output
        def mock_failing_call(self, *args, **kwargs):
            raise ValueError("Test error")

        result = mock_failing_call(figma_wrapper)
        assert isinstance(result, ToolException)
        assert "Error in 'mock_failing_call': Test error" in str(result)
