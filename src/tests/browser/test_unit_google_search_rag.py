import pytest
from unittest.mock import MagicMock, patch
from alita_tools.browser.google_search_rag import GoogleSearchResults, GoogleSearchRag
from langchain_community.utilities.google_search import GoogleSearchAPIWrapper

# Mock data
MOCK_GOOGLE_RESULTS_RAW = [
    {'title': 'Result 1', 'link': 'http://example.com/1', 'snippet': 'Snippet 1'},
    {'title': 'Result 2', 'link': 'http://example.com/2', 'snippet': 'Snippet 2'},
]
MOCK_RAG_RESULT = "Relevant content from scraped pages."

@pytest.mark.unit
@pytest.mark.browser
class TestGoogleSearchTools:

    @pytest.fixture
    def mock_google_api_wrapper(self):
        """Fixture for a mocked GoogleSearchAPIWrapper."""
        mock = MagicMock(spec=GoogleSearchAPIWrapper)
        mock.results.return_value = MOCK_GOOGLE_RESULTS_RAW
        return mock

    @pytest.fixture(autouse=True)
    def mock_web_rag(self):
        """Mock the webRag utility function."""
        with patch('alita_tools.browser.google_search_rag.webRag') as mock_rag:
            mock_rag.return_value = MOCK_RAG_RESULT
            yield mock_rag

    # --- GoogleSearchResults Tests ---
    @pytest.fixture
    def google_search_results_tool(self, mock_google_api_wrapper):
        """Fixture for GoogleSearchResults tool instance."""
        return GoogleSearchResults(api_wrapper=mock_google_api_wrapper, num_results=2) # Use 2 results for test

    @pytest.mark.positive
    def test_google_search_results_run_positive(self, google_search_results_tool, mock_google_api_wrapper):
        query = "Test Query"
        expected_result = str(MOCK_GOOGLE_RESULTS_RAW) # Tool returns string representation

        result = google_search_results_tool._run(query)

        mock_google_api_wrapper.results.assert_called_once_with(query, 2) # num_results=2
        assert result == expected_result

    @pytest.mark.positive
    def test_google_search_results_different_num_results(self, mock_google_api_wrapper):
        """Test tool initialization with different num_results."""
        tool = GoogleSearchResults(api_wrapper=mock_google_api_wrapper, num_results=5)
        query = "Another Query"
        tool._run(query)
        mock_google_api_wrapper.results.assert_called_once_with(query, 5) # Check if correct num_results is used

    # --- GoogleSearchRag Tests ---
    @pytest.fixture
    def google_search_rag_tool(self, mock_google_api_wrapper):
        """Fixture for GoogleSearchRag tool instance."""
        return GoogleSearchRag(googleApiWrapper=mock_google_api_wrapper, num_results=2, max_response_size=5000)

    @pytest.mark.positive
    def test_google_search_rag_run_positive(self, google_search_rag_tool, mock_google_api_wrapper, mock_web_rag):
        query = "Test RAG Query"
        expected_urls = ['http://example.com/1', 'http://example.com/2']
        expected_snippets = "\n\nResult 1\nSnippet 1\n\nResult 2\nSnippet 2"
        expected_result = expected_snippets + MOCK_RAG_RESULT

        result = google_search_rag_tool._run(query)

        mock_google_api_wrapper.results.assert_called_once_with(query, 2) # num_results=2
        mock_web_rag.assert_called_once_with(expected_urls, google_search_rag_tool.max_response_size, query)
        assert result == expected_result

    @pytest.mark.negative
    def test_google_search_rag_run_no_google_results(self, google_search_rag_tool, mock_google_api_wrapper, mock_web_rag):
        query = "Obscure RAG Query"
        mock_google_api_wrapper.results.return_value = [] # Simulate no results
        expected_urls = []
        expected_snippets = ""
        # webRag will be called with empty list, mock should handle this or return empty/specific value
        mock_web_rag.return_value = "No content found from scraping." # Adjust mock return for this case
        expected_result = expected_snippets + "No content found from scraping."

        result = google_search_rag_tool._run(query)

        mock_google_api_wrapper.results.assert_called_once_with(query, 2)
        mock_web_rag.assert_called_once_with(expected_urls, google_search_rag_tool.max_response_size, query)
        assert result == expected_result
