import redis
import json
from flask import current_app

# Use a connection pool for Redis
redis_pool = None


def get_redis_connection():
    """Gets a Redis connection from the connection pool."""
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.ConnectionPool.from_url(
            current_app.config["REDIS_URL"], decode_responses=True
        )
    return redis.Redis(connection_pool=redis_pool)


# --- Wikipedia Link Caching ---


def get_links_from_cache(page_title):
    """Retrieves a list of links for a Wikipedia page from the cache."""
    r = get_redis_connection()
    key = f"wiki_links:{page_title}"
    cached_links = r.get(key)
    return json.loads(cached_links) if cached_links else None


def set_links_in_cache(page_title, links):
    """Stores a list of links for a page in the cache with a 24-hour TTL."""
    r = get_redis_connection()
    key = f"wiki_links:{page_title}"
    # Cache for 24 hours (86400 seconds)
    r.set(key, json.dumps(links), ex=86400)
