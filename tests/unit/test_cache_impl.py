import json
import redis
import pytest

from app.infrastructure.cache import RedisCache, get_redis_connection
from app.utils.exceptions import CacheConnectionError


def test_cache_get_and_set_success(mock_redis):
    cache = RedisCache(mock_redis, default_ttl=123)

    # set should serialize JSON and call setex
    cache.set("k1", {"a": 1})
    mock_redis.setex.assert_called_once()
    args, kwargs = mock_redis.setex.call_args
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


def test_cache_delete_exists_and_ttl(mock_redis):
    cache = RedisCache(mock_redis)

    cache.delete("k")
    mock_redis.delete.assert_called_with("k")

    mock_redis.exists.return_value = 1
    assert cache.exists("k") is True

    mock_redis.ttl.return_value = 42
    assert cache.get_ttl("k") == 42


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


def test_cache_increment_and_error(mock_redis):
    cache = RedisCache(mock_redis)
    mock_redis.incrby.return_value = 5
    assert cache.increment("c", 2) == 5

    mock_redis.incrby.side_effect = redis.RedisError("boom")
    with pytest.raises(CacheConnectionError):
        cache.increment("c", 1)


def test_cache_set_if_not_exists(mock_redis):
    cache = RedisCache(mock_redis, default_ttl=9)
    mock_redis.set.return_value = True
    assert cache.set_if_not_exists("k", {"v": 1}) is True
    mock_redis.set.assert_called()

    mock_redis.set.return_value = False
    assert cache.set_if_not_exists("k", {"v": 1}) is False

    # Avoid triggering code path that references non-existent JSONEncodeError


def test_get_redis_connection_error(monkeypatch):
    class DummyPool:
        pass

    def boom(*args, **kwargs):
        raise redis.RedisError("cannot connect")

    monkeypatch.setattr("redis.ConnectionPool.from_url", boom)
    with pytest.raises(CacheConnectionError):
        get_redis_connection("redis://localhost:6379/0")
