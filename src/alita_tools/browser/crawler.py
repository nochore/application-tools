from json import loads
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import create_model, BaseModel, Field
from .utils import get_page, webRag, getPDFContent

CrawlerModel = create_model(
    "SingleURLCrawlerModel",
    url=(str, Field(description="URL to crawl data from"))
)

class SingleURLCrawler(BaseTool):
    max_response_size: int = 3000
    name: str = "single_url_crawler"
    description: str = "Crawls a single URL and returns the content"
    args_schema = CrawlerModel

    def _run(self, url: str, run_manager=None):
        docs = get_page([url])
        content_parts = []
        current_length = 0
        separator = "\n\n"
        separator_len = len(separator)

        for i, doc in enumerate(docs):
            doc_content = doc.page_content
            doc_len = len(doc_content)
            # Determine if separator is needed (not for the first part)
            needed_separator_len = separator_len if i > 0 else 0

            # Check if adding the next part (with separator) exceeds the limit
            if current_length + needed_separator_len + doc_len > self.max_response_size:
                remaining_space = self.max_response_size - current_length
                # Can we fit the separator and at least one character?
                if remaining_space > needed_separator_len:
                    if i > 0: # Add separator if not the first part
                        content_parts.append(separator)
                    # Add the truncated content
                    content_parts.append(doc_content[:remaining_space - needed_separator_len])
                # If only separator fits or less, we add nothing more.
                break # Stop processing further documents
            else:
                # Add separator if not the first part
                if i > 0:
                    content_parts.append(separator)
                    current_length += separator_len
                # Add the full document content
                content_parts.append(doc_content)
                current_length += doc_len

        return "".join(content_parts)

class MultiURLCrawler(BaseTool):
    max_response_size: int = 3000
    name: str = "multi_url_crawler"
    description: str = "Crawls multiple URLs and returns the content related to query"
    args_schema: Type[BaseModel] = create_model("MultiURLCrawlerModel",
                                                query=(str, Field(description="Query text to search pages")),
                                                urls=(list[str], Field(description="list of URLs to search like ['url1', 'url2']")))

    def _run(self, query: str, urls: list[str], run_manager=None):
        urls = [url.strip() for url in urls]
        return webRag(urls, self.max_response_size, query)


class GetHTMLContent(BaseTool):
    name: str = "get_html_content"
    description: str = "Get HTML content of the page"
    args_schema: Type[BaseModel] = create_model("GetHTMLContentModel",
                                                url=(str, Field(description="URL to get HTML content")))

    def _run(self, url: str, run_manager=None):
        return get_page([url], html_only=True)

class GetPDFContent(BaseTool):
    name: str = "get_pdf_content"
    description: str = "Get PDF content of the page"
    args_schema: Type[BaseModel] = create_model("GetPDFContentModel",
                                                url=(str, Field(description="URL to get PDF content")))
    def _run(self, url: str, run_manager=None):
        try:
            return getPDFContent(url)
        except Exception as e:
            return get_page([url], html_only=True)
