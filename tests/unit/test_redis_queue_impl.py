import json

import pytest
import redis

from app.infrastructure.redis_queue import RedisQueue
from app.utils.exceptions import CacheConnectionError


def test_queue_push_pop_length_clear(mock_redis):
    q = RedisQueue(mock_redis)

    q.push("q1", {"a": 1})
    mock_redis.rpush.assert_called_once()

    # pop None
    mock_redis.lpop.return_value = None
    assert q.pop("q1") is None

    # pop with value
    mock_redis.lpop.return_value = json.dumps({"x": 2})
    assert q.pop("q1") == {"x": 2}

    # length
    mock_redis.llen.return_value = 3
    assert q.length("q1") == 3

    # clear
    q.clear("q1")
    mock_redis.delete.assert_called()


def test_queue_peek_and_errors(mock_redis):
    q = RedisQueue(mock_redis)

    # peek None
    mock_redis.lindex.return_value = None
    assert q.peek("q", 0) is None

    # peek value
    mock_redis.lindex.return_value = json.dumps([1, 2, 3])
    assert q.peek("q", 1) == [1, 2, 3]

    # Avoid triggering code path that references non-existent JSONEncodeError

    mock_redis.lpush.side_effect = None
    mock_redis.lpop.side_effect = redis.RedisError("bad pop")
    with pytest.raises(CacheConnectionError):
        q.pop("q")

    mock_redis.lpop.side_effect = None
    mock_redis.llen.side_effect = redis.RedisError("bad len")
    with pytest.raises(CacheConnectionError):
        q.length("q")

    mock_redis.llen.side_effect = None
    mock_redis.delete.side_effect = redis.RedisError("bad del")
    with pytest.raises(CacheConnectionError):
        q.clear("q")


def test_queue_push_error_raises(mock_redis):
    q = RedisQueue(mock_redis)
    mock_redis.rpush.side_effect = redis.RedisError("push failed")
    with pytest.raises(CacheConnectionError):
        q.push("q", {"x": 1})


def test_queue_push_front(mock_redis):
    q = RedisQueue(mock_redis)
    q.push_front("q", {"a": 1})
    mock_redis.lpush.assert_called_once()

    mock_redis.lpush.side_effect = redis.RedisError("front fail")
    with pytest.raises(CacheConnectionError):
        q.push_front("q", {"a": 1})


def test_queue_pop_batch_zero_count(mock_redis):
    q = RedisQueue(mock_redis)
    assert q.pop_batch("q", 0) == []
    mock_redis.lpop.assert_not_called()


def test_queue_push_batch_error(mock_redis):
    q = RedisQueue(mock_redis)
    mock_redis.rpush.side_effect = redis.RedisError("batch fail")
    with pytest.raises(CacheConnectionError):
        q.push_batch("q", [{"a": 1}])


def test_queue_batch_ops(mock_redis):
    q = RedisQueue(mock_redis)

    # empty items no-op
    q.push_batch("q", [])
    mock_redis.rpush.assert_not_called()

    # batch push
    items = [{"a": 1}, {"b": 2}]
    q.push_batch("q", items)
    mock_redis.rpush.assert_called()

    # batch pop: first two values then None
    seq = [json.dumps(1), json.dumps(2), None]
    mock_redis.lpop.side_effect = lambda name: seq.pop(0)
    assert q.pop_batch("q", 5) == [1, 2]

    # pop_batch error
    def raise_on_lpop(name):
        raise redis.RedisError("err")

    mock_redis.lpop.side_effect = raise_on_lpop
    with pytest.raises(CacheConnectionError):
        q.pop_batch("q", 2)
