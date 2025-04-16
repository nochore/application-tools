import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from alita_tools.browser.crawler import SingleURLCrawler, MultiURLCrawler, GetHTMLContent, GetPDFContent

# Mock data
MOCK_PAGE_CONTENT = "This is the page content."
MOCK_HTML_CONTENT = "<html><body><p>This is HTML.</p></body></html>"
MOCK_PDF_CONTENT = "This is PDF text content."
MOCK_RAG_RESULT = "Relevant content from multiple pages."
MOCK_DOC = [Document(page_content=MOCK_PAGE_CONTENT)]
MOCK_HTML_DOC = [Document(page_content=MOCK_HTML_CONTENT)]
MOCK_HTML_CLEANED = [ # Copied from test_unit_utils.py for use here
    "<html><head></head><body><p>Content 1</p><a href='#'>link</a></body></html>", # Style/script removed
    "<html><body><p>Content 2</p></body></html>"
]

@pytest.mark.unit
@pytest.mark.browser
class TestCrawlers:

    @pytest.fixture(autouse=True)
    def mock_utils(self):
        """Mock utility functions used by the crawlers."""
        with patch('alita_tools.browser.crawler.get_page') as mock_get_page, \
             patch('alita_tools.browser.crawler.webRag') as mock_webRag, \
             patch('alita_tools.browser.crawler.getPDFContent') as mock_getPDFContent:

            # Remove side_effect, set return_value in individual tests
            # mock_get_page.side_effect = lambda urls, html_only=False: MOCK_HTML_DOC if html_only else MOCK_DOC
            mock_webRag.return_value = MOCK_RAG_RESULT
            mock_getPDFContent.return_value = MOCK_PDF_CONTENT

            yield {
                "get_page": mock_get_page,
                "webRag": mock_webRag,
                "getPDFContent": mock_getPDFContent
            }

    # --- SingleURLCrawler Tests ---
    @pytest.fixture
    def single_url_crawler(self):
        return SingleURLCrawler()

    @pytest.mark.positive
    def test_single_url_crawler_run_positive(self, single_url_crawler, mock_utils):
        url = "http://example.com"
        # Set the expected return value for this test
        mock_utils["get_page"].return_value = MOCK_DOC
        result = single_url_crawler._run(url)
        mock_utils["get_page"].assert_called_once_with([url])
        assert result == MOCK_PAGE_CONTENT

    @pytest.mark.positive
    def test_single_url_crawler_run_truncation(self, single_url_crawler, mock_utils):
        url = "http://example.com"
        single_url_crawler.max_response_size = 15 # Set limit for truncation test
        # Simulate get_page returning multiple docs that need concatenation
        doc1_content = "First part." # len 11
        doc2_content = "Second part." # len 12
        mock_utils["get_page"].return_value = [
            Document(page_content=doc1_content),
            Document(page_content=doc2_content)
        ]
        # Expected concatenated content: "First part.\n\nSecond part." (len 11 + 2 + 12 = 25)
        full_concatenated_content = f"{doc1_content}\n\n{doc2_content}"

        result = single_url_crawler._run(url)

        # Now expects the truncated concatenated content
        expected_truncated_content = full_concatenated_content[:single_url_crawler.max_response_size] # "First part.\n\nSe" (len 15)
        assert result == expected_truncated_content
        assert len(result) == single_url_crawler.max_response_size

    @pytest.mark.positive
    def test_single_url_crawler_run_multiple_docs_no_truncation(self, single_url_crawler, mock_utils):
        """Test crawling multiple documents that fit within the size limit."""
        url = "http://example.com"
        # Ensure max_response_size is large enough
        single_url_crawler.max_response_size = 100
        doc1_content = "First document content."
        doc2_content = "Second document content."
        mock_utils["get_page"].return_value = [
            Document(page_content=doc1_content),
            Document(page_content=doc2_content)
        ]
        # Expected result is concatenation with separator
        expected_result = f"{doc1_content}\n\n{doc2_content}"

        result = single_url_crawler._run(url)

        mock_utils["get_page"].assert_called_once_with([url])
        assert result == expected_result
        # Verify length is less than max size
        assert len(result) < single_url_crawler.max_response_size


    # --- MultiURLCrawler Tests ---
    @pytest.fixture
    def multi_url_crawler(self):
        return MultiURLCrawler()

    @pytest.mark.positive
    def test_multi_url_crawler_run_positive(self, multi_url_crawler, mock_utils):
        query = "Search query"
        urls = ["http://example.com/1", " http://example.com/2 "] # Test stripping
        expected_urls = ["http://example.com/1", "http://example.com/2"]
        result = multi_url_crawler._run(query=query, urls=urls)
        mock_utils["webRag"].assert_called_once_with(expected_urls, multi_url_crawler.max_response_size, query)
        assert result == MOCK_RAG_RESULT

    # --- GetHTMLContent Tests ---
    @pytest.fixture
    def get_html_content_tool(self):
        return GetHTMLContent()

    @pytest.mark.positive
    def test_get_html_content_run_positive(self, get_html_content_tool, mock_utils):
        url = "http://example.com"
        # Set the expected return value for this test (html_only=True case)
        # The actual get_page(html_only=True) returns a string, not a list of Docs
        mock_utils["get_page"].return_value = "\n\n".join(MOCK_HTML_CLEANED) # Simulate cleaned HTML string output
        result = get_html_content_tool._run(url)
        mock_utils["get_page"].assert_called_once_with([url], html_only=True)
        # The tool should return the string directly from get_page(html_only=True)
        assert result == "\n\n".join(MOCK_HTML_CLEANED)

    # --- GetPDFContent Tests ---
    @pytest.fixture
    def get_pdf_content_tool(self):
        return GetPDFContent()

    @pytest.mark.positive
    def test_get_pdf_content_run_positive_pdf(self, get_pdf_content_tool, mock_utils):
        url = "http://example.com/doc.pdf"
        result = get_pdf_content_tool._run(url)
        mock_utils["getPDFContent"].assert_called_once_with(url)
        mock_utils["get_page"].assert_not_called()
        assert result == MOCK_PDF_CONTENT

    @pytest.mark.negative
    def test_get_pdf_content_run_pdf_error_fallback_to_html(self, get_pdf_content_tool, mock_utils):
        url = "http://example.com/not_really_a_pdf"
        mock_utils["getPDFContent"].side_effect = Exception("PDF parsing failed")
        # Set the expected return value for the fallback call to get_page
        # The actual get_page(html_only=True) returns a string
        mock_utils["get_page"].return_value = "\n\n".join(MOCK_HTML_CLEANED) # Simulate cleaned HTML string output
        # Expect fallback to get_page
        result = get_pdf_content_tool._run(url)
        mock_utils["getPDFContent"].assert_called_once_with(url)
        mock_utils["get_page"].assert_called_once_with([url], html_only=True)
        # The tool should return the string from the fallback get_page call
        assert result == "\n\n".join(MOCK_HTML_CLEANED)
