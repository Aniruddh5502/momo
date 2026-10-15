from typing import Any
from langchain_core.tools import tool
from momo.tools.registry import ToolContext
import requests
from bs4 import BeautifulSoup
try:
    from ddgs import DDGS                      # current package name
except ImportError:                                # older installs
    from duckduckgo_search import DDGS

def create_web_tools(ctx: ToolContext):
    @tool
    def web_search(query: str) -> str:
        """Searches the web for information using DuckDuckGo.
        
        Args:
            query: The search query string.
        """
        try:
            results = []
            with DDGS() as ddgsSearch:
                searchResults = ddgsSearch.text(query, max_results=5)

                if not searchResults:
                    return f"No web results were found for the query: '{query}'. Try broadening your search terms."

                for i, result in enumerate(searchResults, 1):
                    results.append(f"{i}. Title: {result.get('title')}\nURL: {result.get('href')}\nSnippet: {result.get('body')}\n---")

            return "\n".join(results)

        except Exception as e:
            return f"The search request failed: {str(e)}. This could be due to rate limiting or network issues."

    @tool
    def web_fetch(url: str) -> str:
        """Fetches and extracts text content from a webpage.
        
        Args:
            url: The full URL to fetch.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
                
            text = soup.get_text(separator=" ")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for phrase in lines for phrase in phrase.splitlines())
            text = "\n".join(chunk for chunk in chunks if chunk)
            
            return text[:10000]
        except Exception as e:
            return f"Error fetching URL {url}: {str(e)}"

    return [web_search, web_fetch]