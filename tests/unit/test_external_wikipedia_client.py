from typing import cast
from unittest.mock import Mock

import requests

from app.external.wikipedia import WikipediaClient


class DummyResponse:
    def __init__(self, payload, status=200, raise_exc=None):
        self._payload = payload
        self._status = status
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

    def set_response(self, payload, raise_exc=None):
        self._response = DummyResponse(payload, raise_exc=raise_exc)

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return self._response


def test_get_links_bulk_uses_cache_and_fetch(monkeypatch):
    cache = Mock()
    # one hit, one miss
    cache.get.side_effect = lambda k: ["A"] if k == "wiki_links:Hit" else None

    client = WikipediaClient(cache_service=cache)
    # avoid threads and network: patch _fetch_from_wikipedia
    monkeypatch.setattr(
        client, "_fetch_from_wikipedia", lambda titles: {"Miss": ["B", "C"]}
    )

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


def test_fetch_from_wikipedia_parallel_merge(monkeypatch):
    client = WikipediaClient()
    # Each title is fetched individually via _fetch_single_page; stub it to avoid network
    calls = []

    def fake_fetch_single(title):
        calls.append(title)
        return {title: ["L1", "L2"]}

    monkeypatch.setattr(client, "_fetch_single_page", fake_fetch_single)
    titles = [f"P{i}" for i in range(0, 75)]
    res = client._fetch_from_wikipedia(titles)
    # Every title should have been fetched individually
    assert len(calls) == 75
    assert set(calls) == set(titles)
    # All titles present in merged result
    assert all(t in res for t in titles)
