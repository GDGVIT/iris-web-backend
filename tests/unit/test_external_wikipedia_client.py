from typing import cast
from unittest.mock import Mock

import pytest
import requests

from app.external.wikipedia import WikipediaClient
from app.utils.exceptions import WikipediaAPIError


class DummyResponse:
    def __init__(self, payload, status=200, raise_exc=None):
        self._payload = payload
        self.status_code = status
        self.headers: dict = {}
        self._raise = raise_exc

    def raise_for_status(self):
        if self._raise:
            raise self._raise

    def json(self):
        return self._payload


class DummySession:
    def __init__(self):
        self.headers = {}
        self.calls = []
        self._response = DummyResponse({"query": {}})
        self._raise_exc = None

    def set_response(self, payload, raise_exc=None):
        self._raise_exc = raise_exc
        self._response = DummyResponse(payload)

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if self._raise_exc:
            raise self._raise_exc
        return self._response


def test_get_links_bulk_uses_cache_and_fetch(monkeypatch):
    cache = Mock()
    # one hit, one miss
    cache.get.side_effect = lambda k: ["A"] if k == "wiki_links:Hit" else None

    client = WikipediaClient(cache_service=cache)
    # avoid threads and network: patch _fetch_single_page so _bulk_fetch can use it

    def fake_fetch(title, **kwargs):
        return {title: ["B", "C"] if title == "Miss" else []}

    monkeypatch.setattr(client, "_fetch_single_page", fake_fetch)

    result = client.get_links_bulk(["Hit", "Miss"])
    assert result == {"Hit": ["A"], "Miss": ["B", "C"]}
    # ensure set called for misses
    cache.set.assert_called()


def test_parse_batch_response_redirects_and_filtering():
    client = WikipediaClient()
    data = {
        "redirects": [{"from": "Foo", "to": "Foo (bar)"}],
        "normalized": [{"from": "foo", "to": "Foo (bar)"}],
        "pages": {
            "1": {
                "title": "Foo (bar)",
                "links": [
                    {"title": "Category:Something"},
                    {"title": "File:Image"},
                    {"title": "List of things"},
                    {"title": "Article"},
                ],
            }
        },
    }
    res = client._parse_batch_response(data, ["Foo", "foo", "Other"])
    # category/file filtered out, list allowed
    assert set(res["Foo (bar)"]) == {"List of things", "Article"}
    # mapped back to originals
    assert res["Foo"] == res["Foo (bar)"]
    assert res["foo"] == res["Foo (bar)"]
    # missing page gets empty list
    assert res["Other"] == []


def test_page_exists_and_get_page_info_success_and_failure(monkeypatch):
    session = DummySession()
    client = WikipediaClient(session=cast(requests.Session, session))

    # Page exists
    session.set_response({"query": {"pages": {"1": {"title": "X"}}}})
    assert client.page_exists("X") is True

    # Page missing
    session.set_response({"query": {"pages": {"1": {"title": "X", "missing": True}}}})
    assert client.page_exists("X") is False

    # Request exception -> False
    session.set_response({}, raise_exc=requests.RequestException("bad"))
    assert client.page_exists("X") is False

    # get_page_info success and None cases
    session.set_response(
        {"query": {"pages": {"1": {"title": "T", "pageid": 9, "touched": "2025"}}}}
    )
    info = client.get_page_info("T")
    assert info == {"title": "T", "page_id": 9, "last_modified": "2025"}

    session.set_response({"query": {"pages": {"1": {"title": "T", "missing": True}}}})
    assert client.get_page_info("T") is None

    session.set_response({}, raise_exc=requests.RequestException("oops"))
    assert client.get_page_info("T") is None


def test_get_links_bulk_no_cache_service(monkeypatch):
    """Without a cache service all titles go straight through _bulk_fetch -> _fetch_single_page."""
    client = WikipediaClient()  # no cache_service
    monkeypatch.setattr(
        client,
        "_fetch_single_page",
        lambda title, **kwargs: {title: ["L"]},
    )
    result = client.get_links_bulk(["A", "B"])
    assert result == {"A": ["L"], "B": ["L"]}


def test_get_links_bulk_empty_returns_empty():
    client = WikipediaClient()
    assert client.get_links_bulk([]) == {}


def test_fetch_single_page_success_and_error():
    """_fetch_single_page fetches links and raises WikipediaAPIError on network failure."""
    session = DummySession()
    # max_retries=1 and request_delay=0.0 keep the test instant: no backoff sleep,
    # no rate-limiter sleep.
    client = WikipediaClient(
        session=cast(requests.Session, session), max_retries=1, request_delay=0.0
    )

    # Successful fetch — page with two article links
    session.set_response(
        {
            "query": {
                "pages": {
                    "1": {
                        "title": "Python",
                        "links": [
                            {"title": "Category:Languages"},  # filtered (has colon)
                            {"title": "Guido van Rossum"},
                            {
                                "title": "List of Python topics"
                            },  # kept (starts with "List of")
                        ],
                    }
                }
            }
        }
    )
    result = client._fetch_single_page("Python")
    assert result["Python"] == ["Guido van Rossum", "List of Python topics"]

    # Request error raises WikipediaAPIError
    session.set_response({}, raise_exc=requests.RequestException("timeout"))
    with pytest.raises(WikipediaAPIError):
        client._fetch_single_page("Python")


def test_get_page_with_redirect_info_redirected():
    session = DummySession()
    client = WikipediaClient(session=cast(requests.Session, session))

    session.set_response(
        {
            "query": {
                "redirects": [{"from": "AI", "to": "Artificial intelligence"}],
                "pages": {
                    "1": {
                        "title": "Artificial intelligence",
                        "categories": [],
                    }
                },
            }
        }
    )
    info = client.get_page_with_redirect_info("AI")
    assert info is not None
    assert info["exists"] is True
    assert info["was_redirected"] is True
    assert info["final_title"] == "Artificial intelligence"
    assert info["is_disambiguation"] is False


def test_get_page_with_redirect_info_disambiguation():
    session = DummySession()
    client = WikipediaClient(session=cast(requests.Session, session))

    session.set_response(
        {
            "query": {
                "redirects": [],
                "pages": {
                    "1": {
                        "title": "Mercury",
                        "categories": [{"title": "All disambiguation pages"}],
                    }
                },
            }
        }
    )
    info = client.get_page_with_redirect_info("Mercury")
    assert info is not None
    assert info["exists"] is True
    assert info["is_disambiguation"] is True


def test_get_page_with_redirect_info_missing_and_error():
    session = DummySession()
    client = WikipediaClient(session=cast(requests.Session, session))

    # Missing page
    session.set_response(
        {"query": {"pages": {"1": {"title": "Ghost", "missing": True}}}}
    )
    info = client.get_page_with_redirect_info("Ghost")
    assert info is not None
    assert info["exists"] is False

    # Network error returns safe default
    session.set_response({}, raise_exc=requests.RequestException("net err"))
    info = client.get_page_with_redirect_info("Ghost")
    assert info is not None
    assert info["exists"] is False
    assert info["was_redirected"] is False


def test_bulk_fetch_parallel_merge(monkeypatch):
    """_bulk_fetch dispatches each title to the fetch_fn in parallel and merges results."""
    client = WikipediaClient()
    # Stub _fetch_single_page to avoid network
    calls = []

    def fake_fetch_single(title, **kwargs):
        calls.append(title)
        return {title: ["L1", "L2"]}

    monkeypatch.setattr(client, "_fetch_single_page", fake_fetch_single)
    titles = [f"P{i}" for i in range(0, 75)]
    res = client.get_links_bulk(titles)
    # Every title should have been fetched individually
    assert len(calls) == 75
    assert set(calls) == set(titles)
    # All titles present in merged result
    assert all(t in res for t in titles)
