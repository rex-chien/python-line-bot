import redis
import os

cache = redis.Redis.from_url(os.getenv('REDIS_URL'))


def get_val(name):
    return cache.get(name)


def set_val(name, seconds, value):
    cache.setex(name, seconds, value)
