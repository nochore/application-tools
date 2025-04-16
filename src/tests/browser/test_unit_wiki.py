import pytest
from unittest.mock import MagicMock
from alita_tools.browser.wiki import WikipediaQueryRun, WikipediaAPIWrapper

@pytest.mark.unit
@pytest.mark.browser
class TestWikipediaQueryRun:
    @pytest.fixture
    def mock_api_wrapper(self):
        """Fixture to create a mock WikipediaAPIWrapper."""
        mock = MagicMock(spec=WikipediaAPIWrapper)
        mock.run.return_value = "Mock Wikipedia result for query."
        return mock

    @pytest.fixture
    def wikipedia_tool(self, mock_api_wrapper):
        """Fixture to create an instance of WikipediaQueryRun with a mocked wrapper."""
        return WikipediaQueryRun(api_wrapper=mock_api_wrapper)

    @pytest.mark.positive
    def test_run_positive(self, wikipedia_tool, mock_api_wrapper):
        """Test successful execution of the _run method."""
        query = "Test Query"
        expected_result = "Mock Wikipedia result for query."

        result = wikipedia_tool._run(query)

        mock_api_wrapper.run.assert_called_once_with(query)
        assert result == expected_result

    @pytest.mark.positive
    def test_run_different_query(self, wikipedia_tool, mock_api_wrapper):
        """Test successful execution with a different query."""
        query = "Another Test Query"
        # Modify the mock return value for this specific test if needed,
        # or rely on the default from the fixture.
        mock_api_wrapper.run.return_value = "Specific result for another query."
        expected_result = "Specific result for another query."

        result = wikipedia_tool._run(query)

        mock_api_wrapper.run.assert_called_once_with(query)
        assert result == expected_result

    @pytest.mark.negative
    def test_run_empty_query(self, wikipedia_tool, mock_api_wrapper):
        """Test behavior with an empty query string."""
        query = ""
        # Define expected behavior for empty query based on WikipediaAPIWrapper's actual behavior
        # Assuming it might return an empty string or a specific message
        mock_api_wrapper.run.return_value = "No results found for empty query."
        expected_result = "No results found for empty query."

        result = wikipedia_tool._run(query)

        mock_api_wrapper.run.assert_called_once_with(query)
        assert result == expected_result

    @pytest.mark.negative
    def test_run_api_wrapper_error(self, wikipedia_tool, mock_api_wrapper):
        """Test behavior when the underlying API wrapper returns an error message."""
        query = "Query Causing Error"
        error_message = "Wikipedia API error simulation."
        mock_api_wrapper.run.return_value = error_message # Simulate error message return

        result = wikipedia_tool._run(query)

        mock_api_wrapper.run.assert_called_once_with(query)
        assert result == error_message

    # Example of testing if the wrapper raises an exception, though the current
    # langchain WikipediaAPIWrapper seems to return strings rather than raise.
    # @pytest.mark.negative
    # def test_run_api_wrapper_exception(self, wikipedia_tool, mock_api_wrapper):
    #     """Test behavior when the underlying API wrapper raises an exception."""
    #     query = "Query Causing Exception"
    #     mock_api_wrapper.run.side_effect = Exception("Simulated API Exception")

    #     with pytest.raises(Exception, match="Simulated API Exception"):
    #         wikipedia_tool._run(query)

    #     mock_api_wrapper.run.assert_called_once_with(query)
