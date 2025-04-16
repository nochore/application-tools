import pytest
from unittest.mock import MagicMock, patch, call
from langchain_core.documents import Document
from alita_tools.browser.duck_duck_go_search import DuckDuckGoSearch, searchPages

# Mock data
MOCK_DDG_RESULTS = [
    {'title': 'Result 1', 'href': 'http://example.com/1', 'body': 'Snippet 1'},
    {'title': 'Result 2', 'href': 'http://example.com/2', 'body': 'Snippet 2'},
]
MOCK_HTML_DOCS = [Document(page_content="<html><body><p>Page 1 content</p></body></html>", metadata={'source': 'http://example.com/1'}),
                  Document(page_content="<html><body><p>Page 2 content</p></body></html>", metadata={'source': 'http://example.com/2'})]
MOCK_TRANSFORMED_DOCS = [Document(page_content="Page 1 content", metadata={'source': 'http://example.com/1'}),
                         Document(page_content="Page 2 content", metadata={'source': 'http://example.com/2'})]
MOCK_SPLIT_DOCS = [Document(page_content="Page 1 content"), Document(page_content="Page 2 content")]
MOCK_SEARCH_RESULTS = [Document(page_content="Relevant content 1"), Document(page_content="Relevant content 2")]

@pytest.mark.unit
@pytest.mark.browser
class TestDuckDuckGoSearch:

    @pytest.fixture
    def mock_dependencies(self):
        # Patch DDGS and the webRag function called by the tool
        with patch('alita_tools.browser.duck_duck_go_search.DDGS') as mock_ddgs, \
             patch('alita_tools.browser.duck_duck_go_search.webRag') as mock_web_rag:

            # Configure mocks
            mock_ddgs.return_value.text.return_value = MOCK_DDG_RESULTS
            # Simulate webRag returning the final concatenated/truncated string
            mock_web_rag.return_value = "\n\nRelevant content 1\n\nRelevant content 2"

            yield {
                "ddgs": mock_ddgs,
                "webRag": mock_web_rag
            }

    @pytest.fixture
    def duckduckgo_tool(self):
        """Fixture to create an instance of DuckDuckGoSearch."""
        return DuckDuckGoSearch()

    @pytest.mark.positive
    def test_run_positive(self, duckduckgo_tool, mock_dependencies):
        """Test successful execution of the _run method."""
        query = "Test Query"
        expected_result = "\n\nRelevant content 1\n\nRelevant content 2"

        result = duckduckgo_tool._run(query)

        # Assertions
        mock_dependencies["ddgs"].return_value.text.assert_called_once_with(query, max_results=5)
        # Assert that webRag was called correctly
        expected_urls = ['http://example.com/1', 'http://example.com/2']
        mock_dependencies["webRag"].assert_called_once_with(expected_urls, duckduckgo_tool.max_response_size, query)
        # Assert the final result matches the mocked return value of webRag
        assert result == expected_result

    @pytest.mark.positive
    def test_run_max_response_size(self, duckduckgo_tool, mock_dependencies):
        """Test that the response is truncated based on max_response_size."""
        query = "Test Query"
        duckduckgo_tool.max_response_size = 20 # Smaller than the full mock result
        # Mock webRag to return a truncated result
        expected_result = "\n\nVery long relevant" # Truncated to 20 chars
        mock_dependencies["webRag"].return_value = expected_result

        result = duckduckgo_tool._run(query)

        # Assert webRag was called with the correct max_response_size
        expected_urls = ['http://example.com/1', 'http://example.com/2']
        mock_dependencies["webRag"].assert_called_once_with(expected_urls, duckduckgo_tool.max_response_size, query)
        # Assert the result matches the truncated output from the mocked webRag
        assert result == expected_result
        assert len(result) <= duckduckgo_tool.max_response_size

    @pytest.mark.negative
    def test_run_no_ddg_results(self, duckduckgo_tool, mock_dependencies):
        """Test behavior when DuckDuckGo returns no results."""
        query = "Obscure Query"
        mock_dependencies["ddgs"].return_value.text.return_value = [] # No results
        # Mock webRag to return an empty string when called with no URLs
        expected_result = ""
        mock_dependencies["webRag"].return_value = expected_result

        result = duckduckgo_tool._run(query)

        mock_dependencies["ddgs"].return_value.text.assert_called_once_with(query, max_results=5)
        # Assert webRag was called with an empty list of URLs
        mock_dependencies["webRag"].assert_called_once_with([], duckduckgo_tool.max_response_size, query)
        assert result == expected_result
