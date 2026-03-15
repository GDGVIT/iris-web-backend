import json
from unittest.mock import Mock

import pytest
import redis

from app.infrastructure.cache import RedisCache, get_redis_connection
from app.utils.exceptions import CacheConnectionError


def test_cache_get_and_set_success(mock_redis):
    cache = RedisCache(mock_redis, default_ttl=123)

    # set should serialize JSON and call setex
    cache.set("k1", {"a": 1})
    mock_redis.setex.assert_called_once()
    args, _kwargs = mock_redis.setex.call_args
    assert args[0] == "k1"
    assert args[1] == 123
    assert json.loads(args[2]) == {"a": 1}

    # get should deserialize JSON
    mock_redis.get.return_value = json.dumps({"b": 2})
    assert cache.get("k2") == {"b": 2}


def test_cache_get_miss(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.get.return_value = None
    assert cache.get("missing") is None


def test_cache_get_redis_error_raises_cache_error(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.get.side_effect = redis.RedisError("boom")
    with pytest.raises(CacheConnectionError):
        cache.get("x")


def test_cache_set_success_does_not_raise(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.setex.return_value = True
    cache.set("x", {"y": 1})


def test_cache_delete_exists(mock_redis):
    cache = RedisCache(mock_redis)

    cache.delete("k")
    mock_redis.delete.assert_called_with("k")

    mock_redis.exists.return_value = 1
    assert cache.exists("k") is True


def test_cache_delete_and_exists_error_raises(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.delete.side_effect = redis.RedisError("nope")
    with pytest.raises(CacheConnectionError):
        cache.delete("k")

    mock_redis.delete.side_effect = None
    mock_redis.exists.side_effect = redis.RedisError("bad")
    with pytest.raises(CacheConnectionError):
        cache.exists("k")


def test_cache_clear_pattern(mock_redis):
    cache = RedisCache(mock_redis)

    # No keys
    mock_redis.keys.return_value = []
    assert cache.clear_pattern("p*") == 0

    # Some keys
    mock_redis.keys.return_value = ["a", "b"]
    mock_redis.delete.return_value = 2
    assert cache.clear_pattern("p*") == 2


def test_cache_clear_pattern_error(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.keys.side_effect = redis.RedisError("err")
    with pytest.raises(CacheConnectionError):
        cache.clear_pattern("*")


def test_cache_set_error_raises(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.setex.side_effect = redis.RedisError("write failed")
    with pytest.raises(CacheConnectionError):
        cache.set("k", {"v": 1})


def test_ping_success(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.ping.return_value = True
    assert cache.ping() is True


def test_ping_redis_error_returns_false(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.ping.side_effect = redis.RedisError("connection refused")
    assert cache.ping() is False


def test_delete_many_calls_pipeline(mock_redis):
    cache = RedisCache(mock_redis)
    deleted = []

    class _Pipe:
        def delete(self, key):
            deleted.append(key)
            return self

        def execute(self):
            return [1] * len(deleted)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    mock_redis.pipeline.side_effect = lambda: _Pipe()
    cache.delete_many(["k1", "k2", "k3"])
    assert set(deleted) == {"k1", "k2", "k3"}


def test_delete_many_empty_is_noop(mock_redis):
    cache = RedisCache(mock_redis)
    cache.delete_many([])
    mock_redis.pipeline.assert_not_called()


def test_delete_many_redis_error_raises(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.pipeline.side_effect = redis.RedisError("err")
    with pytest.raises(CacheConnectionError):
        cache.delete_many(["k1"])


def test_set_add(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.sadd = Mock(return_value=1)
    cache.set_add("myset", "value")
    mock_redis.sadd.assert_called_once_with("myset", "value")


def test_set_add_redis_error(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.sadd = Mock(side_effect=redis.RedisError("sadd failed"))
    with pytest.raises(CacheConnectionError):
        cache.set_add("myset", "value")


def test_set_contains_true_and_false(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.sismember = Mock(return_value=True)
    assert cache.set_contains("myset", "value") is True
    mock_redis.sismember.return_value = False
    assert cache.set_contains("myset", "other") is False


def test_set_contains_redis_error(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.sismember = Mock(side_effect=redis.RedisError("sismember failed"))
    with pytest.raises(CacheConnectionError):
        cache.set_contains("myset", "value")


def test_set_add_many_calls_pipeline(mock_redis):
    cache = RedisCache(mock_redis)
    added = []

    class _Pipe:
        def sadd(self, key, val):
            added.append((key, val))
            return self

        def execute(self):
            return [1] * len(added)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    mock_redis.pipeline.side_effect = lambda: _Pipe()
    cache.set_add_many("myset", ["a", "b", "c"])
    assert len(added) == 3
    assert all(key == "myset" for key, _ in added)
    assert {val for _, val in added} == {"a", "b", "c"}


def test_set_add_many_empty_is_noop(mock_redis):
    cache = RedisCache(mock_redis)
    cache.set_add_many("myset", [])
    mock_redis.pipeline.assert_not_called()


def test_set_add_many_redis_error(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.pipeline.side_effect = redis.RedisError("pipeline failed")
    with pytest.raises(CacheConnectionError):
        cache.set_add_many("myset", ["a"])


def test_set_contains_many(mock_redis):
    cache = RedisCache(mock_redis)

    class _Pipe:
        def sismember(self, key, val):
            return self

        def execute(self):
            return [True, False, True]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    mock_redis.pipeline.side_effect = lambda: _Pipe()
    result = cache.set_contains_many("myset", ["a", "b", "c"])
    assert result == [True, False, True]


def test_set_contains_many_empty(mock_redis):
    cache = RedisCache(mock_redis)
    assert cache.set_contains_many("myset", []) == []


def test_set_contains_many_redis_error(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.pipeline.side_effect = redis.RedisError("pipeline failed")
    with pytest.raises(CacheConnectionError):
        cache.set_contains_many("myset", ["a", "b"])


def test_hash_set(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.hset = Mock(return_value=1)
    cache.hash_set("myhash", "field", "value")
    mock_redis.hset.assert_called_once_with("myhash", "field", "value")


def test_hash_set_redis_error(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.hset = Mock(side_effect=redis.RedisError("hset failed"))
    with pytest.raises(CacheConnectionError):
        cache.hash_set("myhash", "field", "value")


def test_hash_get_str_value(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.hget = Mock(return_value="value")
    assert cache.hash_get("myhash", "field") == "value"


def test_hash_get_bytes_decoded(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.hget = Mock(return_value=b"value")
    assert cache.hash_get("myhash", "field") == "value"


def test_hash_get_missing_returns_none(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.hget = Mock(return_value=None)
    assert cache.hash_get("myhash", "field") is None


def test_hash_get_redis_error(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.hget = Mock(side_effect=redis.RedisError("hget failed"))
    with pytest.raises(CacheConnectionError):
        cache.hash_get("myhash", "field")


def test_hash_set_many(mock_redis):
    cache = RedisCache(mock_redis)
    calls = []

    class _Pipe:
        def hset(self, key, field, val):
            calls.append((key, field, val))
            return self

        def execute(self):
            return [1] * len(calls)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    mock_redis.pipeline.side_effect = lambda: _Pipe()
    cache.hash_set_many("myhash", {"f1": "v1", "f2": "v2"})
    assert len(calls) == 2
    assert all(key == "myhash" for key, _, _ in calls)
    fields = {f for _, f, _ in calls}
    assert fields == {"f1", "f2"}


def test_hash_set_many_empty_is_noop(mock_redis):
    cache = RedisCache(mock_redis)
    cache.hash_set_many("myhash", {})
    mock_redis.pipeline.assert_not_called()


def test_hash_set_many_redis_error(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.pipeline.side_effect = redis.RedisError("pipeline failed")
    with pytest.raises(CacheConnectionError):
        cache.hash_set_many("myhash", {"f": "v"})


def test_get_redis_connection_error(monkeypatch):
    class DummyPool:
        pass

    def boom(*args, **kwargs):
        raise redis.RedisError("cannot connect")

    monkeypatch.setattr("redis.ConnectionPool.from_url", boom)
    with pytest.raises(CacheConnectionError):
        get_redis_connection("redis://localhost:6379/0")
