import json
import logging
import os

from langchain_core.tools import BaseTool, tool
from tavily import AsyncTavilyClient

from src.log_context import log_context

logger = logging.getLogger(__name__)
SEARCH_UNAVAILABLE = "Web search unavailable. No external evidence was retrieved from this search."
SEARCH_TIMEOUT_SECONDS = 30
MAX_SEARCH_RESULTS = 5


def build_search_tool() -> BaseTool:
    api_key = os.environ["TAVILY_API_KEY"]
    if not api_key:
        raise ValueError("TAVILY_API_KEY must not be empty")

    @tool("tavily_search")
    async def search(query: str) -> str:
        """Search the web for evidence with source titles, URLs, and snippets."""
        logger.info("%s stage=search event=start", log_context())
        try:
            async with AsyncTavilyClient(api_key=api_key) as client:
                response = await client.search(
                    query=query,
                    search_depth="basic",
                    max_results=MAX_SEARCH_RESULTS,
                    timeout=SEARCH_TIMEOUT_SECONDS,
                )
            results = [
                {"title": item["title"], "url": item["url"], "content": item["content"]}
                for item in response["results"]
            ]
        except Exception as error:
            logger.warning("%s stage=search event=failed error_type=%s", log_context(), type(error).__name__)
            return json.dumps({"results": [], "error": SEARCH_UNAVAILABLE})
        logger.info("%s stage=search event=completed results=%d", log_context(), len(results))
        return json.dumps({"results": results})

    return search
