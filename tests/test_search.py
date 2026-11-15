import json
import unittest
from unittest.mock import patch

from celery.exceptions import SoftTimeLimitExceeded

from src.agent.tools.search import MAX_SEARCH_RESULTS, SEARCH_TIMEOUT_SECONDS, search


class SearchTests(unittest.TestCase):
    def test_returns_only_source_fields_and_closes_client(self) -> None:
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}), patch("src.agent.tools.search.TavilyClient") as client:
            provider = client.return_value.__enter__.return_value.search
            provider.return_value = {"results": [{
                "title": "Source", "url": "https://example.org", "content": "Evidence", "score": 0.9,
            }], "request_id": "private"}

            result = json.loads(search.invoke({"query": "claim"}))

        self.assertEqual(result, {"results": [{"title": "Source", "url": "https://example.org", "content": "Evidence"}]})
        client.assert_called_once_with(api_key="test-key")
        provider.assert_called_once_with(query="claim", search_depth="basic", max_results=MAX_SEARCH_RESULTS, timeout=SEARCH_TIMEOUT_SECONDS)
        client.return_value.__exit__.assert_called_once()

    def test_rejects_missing_or_empty_credentials(self) -> None:
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(KeyError):
            search.invoke({"query": "claim"})
        with (
            patch.dict("os.environ", {"TAVILY_API_KEY": ""}),
            self.assertRaisesRegex(ValueError, "must not be empty"),
        ):
            search.invoke({"query": "claim"})

    def test_empty_search_results_are_valid(self) -> None:
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}), patch("src.agent.tools.search.TavilyClient") as client:
            client.return_value.__enter__.return_value.search.return_value = {"results": []}
            self.assertEqual(json.loads(search.invoke({"query": "claim"})), {"results": []})

    def test_search_failure_is_generic_but_logged(self) -> None:
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}), patch("src.agent.tools.search.TavilyClient") as client:
            client.return_value.__enter__.return_value.search.side_effect = RuntimeError("Provider unavailable")
            with self.assertLogs("src.agent.tools.search", level="ERROR"):
                result = json.loads(search.invoke({"query": "claim"}))
        self.assertEqual(result["results"], [])
        self.assertIn("Web search unavailable", result["error"])
        self.assertNotIn("Provider unavailable", result["error"])

    def test_soft_time_limit_is_not_masked(self) -> None:
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}), patch("src.agent.tools.search.TavilyClient") as client:
            client.return_value.__enter__.return_value.search.side_effect = SoftTimeLimitExceeded()
            with self.assertRaises(SoftTimeLimitExceeded):
                search.invoke({"query": "claim"})
