import json
import logging
import os

from celery.exceptions import SoftTimeLimitExceeded
from langchain_core.tools import tool
from tavily import TavilyClient

from src.log_context import task_id

SEARCH_TIMEOUT_SECONDS = 30
MAX_SEARCH_RESULTS = 5
SEARCH_UNAVAILABLE = "Web search unavailable. No external evidence was retrieved from this search."
logger = logging.getLogger(__name__)


@tool("tavily_search")
def search(query: str) -> str:
    """Search the web for evidence with source titles, URLs, and snippets."""
    api_key = os.environ["TAVILY_API_KEY"]
    if not api_key:
        raise ValueError("TAVILY_API_KEY must not be empty")
    try:
        with TavilyClient(api_key=api_key) as client:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=MAX_SEARCH_RESULTS,
                timeout=SEARCH_TIMEOUT_SECONDS,
            )
        results = [
            {"title": item["title"], "url": item["url"], "content": item["content"]}
            for item in response["results"]
        ]
    except SoftTimeLimitExceeded:
        raise
    except Exception:
        logger.exception("task_id=%s stage=search event=failed", task_id.get())
        return json.dumps({"results": [], "error": SEARCH_UNAVAILABLE})
    return json.dumps({"results": results})
