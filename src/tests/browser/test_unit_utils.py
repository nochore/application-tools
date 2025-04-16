import pytest
from unittest.mock import patch, MagicMock, call
from langchain_core.documents import Document
import fitz # PyMuPDF
import requests

from alita_tools.browser.utils import get_page, webRag, getPDFContent

# Mock data for get_page
MOCK_URLS = ['http://example.com/1', 'http://example.com/2']
MOCK_HTML_DOCS_RAW = [
    Document(page_content="<html><head><style>css</style><script>js</script></head><body><p>Content 1</p><a href='#'>link</a></body></html>", metadata={'source': MOCK_URLS[0]}),
    Document(page_content="<html><body><p>Content 2</p></body></html>", metadata={'source': MOCK_URLS[1]})
]
MOCK_HTML_CLEANED = [
    "<html><head></head><body><p>Content 1</p><a href='#'>link</a></body></html>", # Style/script removed
    "<html><body><p>Content 2</p></body></html>"
]
MOCK_TRANSFORMED_DOCS = [
    Document(page_content="Content 1", metadata={'source': MOCK_URLS[0]}),
    Document(page_content="Content 2", metadata={'source': MOCK_URLS[1]})
]

# Mock data for webRag
MOCK_SPLIT_DOCS_RAG = [Document(page_content="Content 1"), Document(page_content="Content 2")]
MOCK_SEARCH_RESULTS_RAG = [Document(page_content="Relevant content 1"), Document(page_content="Relevant content 2")]

# Mock data for getPDFContent
MOCK_PDF_URL = "http://example.com/doc.pdf"
MOCK_PDF_BYTES = b'%PDF-1.4...' # Dummy PDF bytes
MOCK_PDF_TEXT = "Text extracted from PDF page 1. Text from page 2."


@pytest.mark.unit
@pytest.mark.browser
class TestBrowserUtils:

    # --- get_page Tests ---
    @pytest.fixture
    def mock_get_page_deps(self):
        with patch('alita_tools.browser.utils.AsyncChromiumLoader') as mock_loader, \
             patch('alita_tools.browser.utils.BeautifulSoupTransformer') as mock_transformer:

            mock_loader.return_value.load.return_value = MOCK_HTML_DOCS_RAW
            mock_transformer.return_value.transform_documents.return_value = MOCK_TRANSFORMED_DOCS

            yield {"loader": mock_loader, "transformer": mock_transformer}

    @pytest.mark.positive
    def test_get_page_extract_text(self, mock_get_page_deps):
        """Test get_page for standard text extraction."""
        result = get_page(MOCK_URLS)

        mock_get_page_deps["loader"].assert_called_once_with(MOCK_URLS)
        mock_get_page_deps["loader"].return_value.load.assert_called_once()
        mock_get_page_deps["transformer"].assert_called_once()
        mock_get_page_deps["transformer"].return_value.transform_documents.assert_called_once_with(
            MOCK_HTML_DOCS_RAW, tags_to_extract=["p"], remove_unwanted_tags=["a"]
        )
        assert result == MOCK_TRANSFORMED_DOCS

    @pytest.mark.positive
    def test_get_page_html_only(self, mock_get_page_deps):
        """Test get_page with html_only=True."""
        result = get_page(MOCK_URLS, html_only=True)

        mock_get_page_deps["loader"].assert_called_once_with(MOCK_URLS)
        mock_get_page_deps["loader"].return_value.load.assert_called_once()
        mock_get_page_deps["transformer"].assert_not_called() # Transformer should not be used

        # Check if style/script tags are removed and content is joined
        expected_html_output = "\n\n".join(MOCK_HTML_CLEANED)
        assert result == expected_html_output

    @pytest.mark.negative
    def test_get_page_loader_error(self, mock_get_page_deps):
        """Test get_page when loader fails."""
        mock_get_page_deps["loader"].return_value.load.side_effect = Exception("Load failed")
        with pytest.raises(Exception, match="Load failed"):
            get_page(MOCK_URLS)

    # --- webRag Tests ---
    @pytest.fixture
    def mock_web_rag_deps(self):
         # Patch get_page within the webRag function's scope
        with patch('alita_tools.browser.utils.get_page') as mock_get_page_for_rag, \
             patch('alita_tools.browser.utils.CharacterTextSplitter') as mock_splitter, \
             patch('alita_tools.browser.utils.SentenceTransformerEmbeddings') as mock_embeddings, \
             patch('alita_tools.browser.utils.Chroma') as mock_chroma:

            mock_get_page_for_rag.return_value = MOCK_TRANSFORMED_DOCS # Simulate get_page returning docs
            mock_splitter.return_value.split_documents.return_value = MOCK_SPLIT_DOCS_RAG
            mock_embeddings.return_value = MagicMock()
            mock_chroma_instance = MagicMock()
            mock_chroma.from_documents.return_value = mock_chroma_instance
            mock_chroma_instance.search.return_value = MOCK_SEARCH_RESULTS_RAG

            yield {
                "get_page": mock_get_page_for_rag,
                "splitter": mock_splitter,
                "embeddings": mock_embeddings,
                "chroma": mock_chroma
            }

    @pytest.mark.positive
    def test_web_rag_positive(self, mock_web_rag_deps):
        """Test successful execution of webRag."""
        query = "Test Query"
        max_size = 5000
        expected_result = "\n\nRelevant content 1\n\nRelevant content 2"

        result = webRag(MOCK_URLS, max_size, query)

        mock_web_rag_deps["get_page"].assert_called_once_with(MOCK_URLS)
        mock_web_rag_deps["splitter"].assert_called_once_with(chunk_size=1000, chunk_overlap=0)
        mock_web_rag_deps["splitter"].return_value.split_documents.assert_called_once_with(MOCK_TRANSFORMED_DOCS)
        mock_web_rag_deps["embeddings"].assert_called_once_with(model_name="all-MiniLM-L6-v2")
        mock_web_rag_deps["chroma"].from_documents.assert_called_once_with(MOCK_SPLIT_DOCS_RAG, mock_web_rag_deps["embeddings"].return_value)
        mock_web_rag_deps["chroma"].from_documents.return_value.search.assert_called_once_with(query, "mmr", k=10)
        assert result == expected_result

    @pytest.mark.positive
    def test_web_rag_truncation(self, mock_web_rag_deps):
        """Test webRag response truncation."""
        query = "Test Query"
        max_size = 20 # Smaller than full result
        # Mock search results that would exceed the limit
        long_results = [Document(page_content="Very long relevant content part 1"), Document(page_content="Part 2")]
        mock_web_rag_deps["chroma"].from_documents.return_value.search.return_value = long_results
        # Expected result should be truncated precisely at max_size
        # Original content: "\n\nVery long relevant content part 1" (len 35)
        expected_result = "\n\nVery long relevant" # Truncated to 20 chars

        result = webRag(MOCK_URLS, max_size, query)

        assert result == expected_result
        assert len(result) <= max_size # Should be exactly <= max_size

    # --- getPDFContent Tests ---
    @pytest.fixture
    def mock_pdf_deps(self):
        with patch('alita_tools.browser.utils.requests.get') as mock_requests_get, \
             patch('alita_tools.browser.utils.fitz.open') as mock_fitz_open:

            # Mock requests response
            mock_response = MagicMock(spec=requests.Response)
            mock_response.status_code = 200
            mock_response.content = MOCK_PDF_BYTES
            mock_requests_get.return_value = mock_response

            # Mock fitz document and pages
            mock_pdf_doc = MagicMock(spec=fitz.Document)
            mock_page1 = MagicMock(spec=fitz.Page)
            mock_page1.get_text.return_value = "Text extracted from PDF page 1. "
            mock_page2 = MagicMock(spec=fitz.Page)
            mock_page2.get_text.return_value = "Text from page 2."
            mock_pages = [mock_page1, mock_page2]
            # Simulate __len__ and __getitem__ for iteration
            mock_pdf_doc.__len__.return_value = len(mock_pages)
            # Use a function for side_effect to avoid premature consumption by assertions
            mock_pdf_doc.__getitem__.side_effect = lambda index: mock_pages[index]

            mock_fitz_open.return_value = mock_pdf_doc

            yield {"requests_get": mock_requests_get, "fitz_open": mock_fitz_open, "pdf_doc": mock_pdf_doc, "mock_pages": mock_pages}

    @pytest.mark.positive
    def test_get_pdf_content_positive(self, mock_pdf_deps):
        """Test successful PDF download and text extraction."""
        result = getPDFContent(MOCK_PDF_URL)

        mock_pdf_deps["requests_get"].assert_called_once_with(MOCK_PDF_URL)
        mock_pdf_deps["fitz_open"].assert_called_once_with(stream=MOCK_PDF_BYTES, filetype="pdf")
        # Check if get_text was called for each mock page instance directly
        mock_pdf_deps["mock_pages"][0].get_text.assert_called_once()
        mock_pdf_deps["mock_pages"][1].get_text.assert_called_once()
        mock_pdf_deps["pdf_doc"].close.assert_called_once()
        assert result == MOCK_PDF_TEXT

    @pytest.mark.negative
    def test_get_pdf_content_download_error(self, mock_pdf_deps):
        """Test handling of failed PDF download."""
        mock_response = mock_pdf_deps["requests_get"].return_value
        mock_response.status_code = 404
        mock_response.content = b'' # No content on error

        result = getPDFContent(MOCK_PDF_URL)

        mock_pdf_deps["requests_get"].assert_called_once_with(MOCK_PDF_URL)
        mock_pdf_deps["fitz_open"].assert_not_called() # fitz.open should not be called
        assert result is None # Function returns None on download failure

    @pytest.mark.negative
    def test_get_pdf_content_parsing_error(self, mock_pdf_deps):
        """Test handling of error during PDF parsing (fitz.open)."""
        # Simulate fitz.open raising a RuntimeError (common for PyMuPDF errors)
        mock_pdf_deps["fitz_open"].side_effect = RuntimeError("Invalid PDF")

        # Expect RuntimeError
        with pytest.raises(RuntimeError, match="Invalid PDF"):
             getPDFContent(MOCK_PDF_URL)

        mock_pdf_deps["requests_get"].assert_called_once_with(MOCK_PDF_URL)
        mock_pdf_deps["fitz_open"].assert_called_once_with(stream=MOCK_PDF_BYTES, filetype="pdf")
        mock_pdf_deps["pdf_doc"].close.assert_not_called() # Close won't be reached if open fails
