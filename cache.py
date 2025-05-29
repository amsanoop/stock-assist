import hashlib
import json
import zlib
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from flask import Response, jsonify, request
from redis import Redis

redis_client: Optional[Redis] = None


def init_redis(app) -> None:
    """Initialize Redis connection.

    Args:
        app: Flask application instance.
    """
    global redis_client
    redis_client = Redis(
        host=app.config.get("REDIS_HOST", "localhost"),
        port=app.config.get("REDIS_PORT", 6379),
        db=app.config.get("REDIS_DB", 0),
        socket_timeout=5,
        socket_connect_timeout=5,
        health_check_interval=30,
    )
    

def cached(timeout: int = 300, include_query_params: bool = False) -> Callable:
    """Decorator to cache function results in Redis.

    Args:
        timeout (int): Cache timeout in seconds. Defaults to 300.
        include_query_params (bool): Whether to include query parameters in cache key.

    Returns:
        Callable: Decorated function.
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            """Decorated function to handle caching.

            Args:
                *args (Any): Positional arguments passed to the original function.
                **kwargs (Any): Keyword arguments passed to the original function.

            Returns:
                Any: Result from cache or original function.
            """
            if not redis_client:
                return f(*args, **kwargs)

            query_params = ""
            if include_query_params and request:
                query_params = str(request.args)

            key_data = f"{f.__name__}:{str(args)}:{str(kwargs)}:{query_params}"
            key = f"cache:{hashlib.md5(key_data.encode()).hexdigest()}"

            try:
                cached_data = redis_client.get(key)
                if cached_data is not None:
                    if cached_data.startswith(b"COMPRESSED:"):
                        compressed_data = cached_data[11:]
                        decompressed_data = zlib.decompress(compressed_data)
                        cached_result = json.loads(decompressed_data)
                    else:
                        cached_result = json.loads(cached_data)

                    if isinstance(cached_result, dict) and "status_code" in cached_result:
                        return jsonify(cached_result["data"]), cached_result["status_code"]
                    return jsonify(cached_result)
            except Exception as e:
                print(f"Cache retrieval error: {str(e)}")

            result = f(*args, **kwargs)

            try:
                if isinstance(result, tuple):
                    response_data = json.loads(result[0].get_data())
                    status_code = result[1]
                    cache_data = {"data": response_data, "status_code": status_code}
                elif isinstance(result, Response):
                    response_data = json.loads(result.get_data())
                    cache_data = response_data
                else:
                    cache_data = result

                json_data = json.dumps(cache_data)
                if len(json_data) > 1024:
                    compressed = zlib.compress(json_data.encode())
                    redis_client.setex(key, timeout, b"COMPRESSED:" + compressed)
                else:
                    redis_client.setex(key, timeout, json_data)
            except Exception as e:
                print(f"Caching error: {str(e)}")

            return result

        return decorated

    return decorator


def cache_db_query(query_key: str, data: Union[Dict, List], timeout: int = 300) -> bool:
    """Cache database query results in Redis.

    Args:
        query_key (str): Unique key for the query.
        data (Union[Dict, List]): Data to cache.
        timeout (int): Cache timeout in seconds. Defaults to 300.

    Returns:
        bool: True if caching was successful, False otherwise.
    """
    if not redis_client:
        return False

    try:
        key = f"db:{hashlib.md5(query_key.encode()).hexdigest()}"
        json_data = json.dumps(data)

        if len(json_data) > 1024:
            compressed = zlib.compress(json_data.encode())
            redis_client.setex(key, timeout, b"COMPRESSED:" + compressed)
        else:
            redis_client.setex(key, timeout, json_data)
        return True
    except Exception as e:
        print(f"DB caching error: {str(e)}")
        return False


def get_cached_query(query_key: str) -> Optional[Union[Dict, List]]:
    """Retrieve cached database query results from Redis.

    Args:
        query_key (str): Unique key for the query.

    Returns:
        Optional[Union[Dict, List]]: Cached data or None if not found.
    """
    if not redis_client:
        return None

    try:
        key = f"db:{hashlib.md5(query_key.encode()).hexdigest()}"
        cached_data = redis_client.get(key)

        if cached_data is None:
            return None

        if cached_data.startswith(b"COMPRESSED:"):
            compressed_data = cached_data[11:]
            decompressed_data = zlib.decompress(compressed_data)
            return json.loads(decompressed_data)

        return json.loads(cached_data)
    except Exception as e:
        print(f"Cache retrieval error: {str(e)}")
        return None


def invalidate_cache_pattern(pattern: str) -> int:
    """Invalidate all cache keys matching a pattern.

    Args:
        pattern (str): Pattern to match keys against.

    Returns:
        int: Number of keys invalidated.
    """
    if not redis_client:
        return 0

    try:
        keys = redis_client.keys(pattern)
        if keys:
            return redis_client.delete(*keys)
        return 0
    except Exception as e:
        print(f"Cache invalidation error: {str(e)}")
        return 0
