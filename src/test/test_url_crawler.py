# tests/url_crawler/test_url_crawler.py

"""Tests for the url_krawler_graph."""

from unittest.mock import AsyncMock, patch

import pytest

# Imports are relative to the src directory (configured in pyproject.toml pythonpath)
from url_crawler.url_krawler_graph import url_crawler_app


@pytest.fixture
def sample_input_state() -> dict:
    """Provide a sample input state for the url_crawler_app graph."""
    return {
        "url": "https://www.britannica.com/biography/Henry-Miller",
        "research_question": "Research the life of Henry Miller",
    }


@pytest.fixture
def mock_scraped_content():
    """Provide mock scraped content for testing."""
    return """
    Henry Miller was an American novelist, short story writer and essayist. 
    He was born in Yorkville, NYC on December 26, 1891. 
    He moved to Paris in 1930 where he lived for many years.
    He wrote Tropic of Cancer, part of his series of novels about his life.
    He married his first wife Beatrice in 1917.
    He had a daughter named Barbara in 1919.
    He divorced Beatrice in 1924.
    He married his second wife June in 1924.
    He died in Pacific Palisades, California on June 7, 1980.
    """


@pytest.mark.asyncio
async def test_url_crawler_with_mocked_llm(
    sample_input_state: dict,
    mock_scraped_content: str,
):
    """Unit test for the simplified URL crawler graph."""
    # --- Act: Execute the graph with patched dependencies ---
    with patch("url_crawler.url_krawler_graph.url_crawl") as mock_crawl:
        # Configure URL crawling mock
        mock_crawl.return_value = mock_scraped_content

        result = await url_crawler_app.ainvoke(sample_input_state)

    # --- Assert: Verify the output ---
    assert "extracted_events" in result
    assert "raw_scraped_content" in result

    extracted_events = result["extracted_events"]
    raw_scraped_content = result["raw_scraped_content"]

    # Verify that the scraped content is returned
    assert extracted_events == mock_scraped_content
    assert raw_scraped_content == mock_scraped_content

    # Verify that url_crawl was called with the correct URL
    mock_crawl.assert_called_once_with(sample_input_state["url"])


@pytest.mark.asyncio
async def test_url_crawler_with_mocked_url_crawling(
    sample_input_state: dict,
    mock_scraped_content: str,
):
    """Test URL crawler with mocked URL crawling."""
    # --- Act: Execute with mocked URL crawling ---
    with patch("url_crawler.url_krawler_graph.url_crawl") as mock_crawl:
        # Configure URL crawling mock
        mock_crawl.return_value = mock_scraped_content

        result = await url_crawler_app.ainvoke(sample_input_state)

    # --- Assert: Verify the output ---
    assert "extracted_events" in result
    assert "raw_scraped_content" in result

    extracted_events = result["extracted_events"]
    raw_scraped_content = result["raw_scraped_content"]

    # Verify that the scraped content is returned correctly
    assert extracted_events == mock_scraped_content
    assert raw_scraped_content == mock_scraped_content

    # Verify that url_crawl was called with the correct URL
    mock_crawl.assert_called_once_with(sample_input_state["url"])


@pytest.mark.asyncio
async def test_url_crawler_with_empty_content():
    """Test URL crawler with empty scraped content."""
    input_state = {
        "url": "https://example.com/empty",
        "research_question": "Test question",
    }

    with patch("url_crawler.url_krawler_graph.url_crawl") as mock_crawl:
        # Configure URL crawling mock to return empty content
        mock_crawl.return_value = ""

        result = await url_crawler_app.ainvoke(input_state)

    # --- Assert: Verify the output ---
    assert "extracted_events" in result
    assert "raw_scraped_content" in result

    # Should return empty content
    assert result["extracted_events"] == ""
    assert result["raw_scraped_content"] == ""


@pytest.mark.asyncio
async def test_url_crawler_with_long_content():
    """Test URL crawler with content longer than MAX_CONTENT_LENGTH."""
    input_state = {
        "url": "https://example.com/long",
        "research_question": "Test question",
    }

    # Create content longer than typical MAX_CONTENT_LENGTH
    long_content = "This is a very long content. " * 10000  # Much longer than limit

    with patch("url_crawler.url_krawler_graph.url_crawl") as mock_crawl:
        # Configure URL crawling mock to return long content
        mock_crawl.return_value = long_content

        result = await url_crawler_app.ainvoke(input_state)

    # --- Assert: Verify the output ---
    assert "extracted_events" in result
    assert "raw_scraped_content" in result

    # Content should be truncated to MAX_CONTENT_LENGTH
    returned_content = result["extracted_events"]
    assert len(returned_content) <= len(long_content)
    assert returned_content == result["raw_scraped_content"]