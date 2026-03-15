from types import SimpleNamespace
from unittest.mock import Mock

from app import create_app
from app.core.factory import ServiceFactory
from app.infrastructure.tasks import configure_periodic_tasks, configure_task_routes
from config.testing import TestingConfig


def test_service_factory_lifecycle(monkeypatch):
    app = create_app(TestingConfig)
    with app.app_context():
        fake_redis = Mock()

        # ensure clean slate
        ServiceFactory.cleanup()

        # patch redis connection creation
        monkeypatch.setattr(
            "app.core.factory.get_redis_connection", lambda url: fake_redis
        )

        r1 = ServiceFactory.get_redis_client()
        assert r1 is fake_redis

        cache = ServiceFactory.get_cache_service()
        assert cache._redis_client is fake_redis
        assert cache.default_ttl == app.config.get("CACHE_TTL")

        queue = ServiceFactory.get_queue_service()
        assert queue._redis_client is fake_redis

        wiki = ServiceFactory.get_wikipedia_client()
        # wikipedia client should have cache and configured workers
        assert wiki.cache_service is cache
        assert wiki.max_workers == app.config.get("WIKIPEDIA_MAX_WORKERS")

        # create services
        pf = ServiceFactory.create_pathfinding_service("bfs")
        assert pf is not None
        ws = ServiceFactory.create_wikipedia_service()
        assert ws is not None
        cms = ServiceFactory.create_cache_management_service()
        assert cms is not None

        # cleanup closes redis
        fake_redis.close = Mock()
        ServiceFactory.cleanup()
        fake_redis.close.assert_called_once()


def test_configure_task_routes_and_periodic_tasks():
    class Dummy:
        def __init__(self):
            self.conf = SimpleNamespace()

    app = Dummy()
    configure_task_routes(app)
    assert isinstance(app.conf.task_routes, dict)
    assert "app.infrastructure.tasks.find_path_task" in app.conf.task_routes
    assert app.conf.result_expires == 3600
    assert app.conf.result_persistent is True
    assert app.conf.task_reject_on_worker_lost is True

    configure_periodic_tasks(app)
    assert isinstance(app.conf.beat_schedule, dict)
    assert app.conf.timezone == "UTC"
