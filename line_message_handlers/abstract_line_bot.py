import os
from linebot import (
    LineBotApi, WebhookHandler
)
from pymongo import MongoClient
import redis
import abc


class AbstractLineMessageHandler(abc.ABC):
    line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
    handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))
    mongo_dbname = os.getenv('MONGODB_DATABASE')
    client = MongoClient(os.getenv('MONGODB_URI') + '/' + mongo_dbname)
    db = client[mongo_dbname]
    redis_cache = redis.Redis.from_url(os.getenv('REDIS_URL'))

    def __init__(self):
        pass

    def get_collection(self, collection_name):
        return self.db[collection_name]

    @abc.abstractmethod
    def handle_event(self, event):
        return NotImplemented
