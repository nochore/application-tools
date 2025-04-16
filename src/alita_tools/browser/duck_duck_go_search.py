from typing import Type
from duckduckgo_search import DDGS
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

# Import the required utility function
from .utils import webRag


class searchPages(BaseModel):
    query: str = Field(..., title="Query text to search pages")

class DuckDuckGoSearch(BaseTool):
    name: str = "DuckDuckGo_Search"
    max_response_size: int = 3000
    description: str = "Searches DuckDuckGo for the query and returns the top 5 results, and them provide summary documents"
    args_schema: Type[BaseModel] = searchPages

    def _run(self, query: str, run_manager=None):
        default_k = 5
        results = DDGS().text(query, max_results=default_k)
        urls = []
        for result in results:
            url = result['href']
            urls.append(url)

        # Call the centralized webRag function
        return webRag(urls, self.max_response_size, query)


