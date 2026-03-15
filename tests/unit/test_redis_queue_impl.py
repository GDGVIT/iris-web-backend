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


def test_queue_errors(mock_redis):
    q = RedisQueue(mock_redis)

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


def test_queue_pop_batch_zero_count(mock_redis):
    q = RedisQueue(mock_redis)
    assert q.pop_batch("q", 0) == []
    mock_redis.lpop.assert_not_called()


def test_queue_push_batch_error(mock_redis):
    q = RedisQueue(mock_redis)
    # Make the pipeline context manager raise a RedisError
    mock_redis.pipeline.side_effect = redis.RedisError("batch fail")
    with pytest.raises(CacheConnectionError):
        q.push_batch("q", [{"a": 1}])


def test_queue_batch_ops(mock_redis):
    q = RedisQueue(mock_redis)

    # empty items no-op
    q.push_batch("q", [])
    mock_redis.rpush.assert_not_called()

    # batch push — pipeline calls rpush for each item
    items = [{"a": 1}, {"b": 2}]
    q.push_batch("q", items)
    assert mock_redis.rpush.call_count == len(items)

    # batch pop: pipeline issues exactly `count` lpop calls; None values are filtered.
    # Provide enough values to cover all 5 pipeline calls.
    seq = [json.dumps(1), json.dumps(2), None, None, None]
    mock_redis.lpop.side_effect = lambda name: seq.pop(0)
    assert q.pop_batch("q", 5) == [1, 2]

    # pop_batch error: pipeline itself raises
    mock_redis.lpop.side_effect = None
    mock_redis.pipeline.side_effect = redis.RedisError("err")
    with pytest.raises(CacheConnectionError):
        q.pop_batch("q", 2)
