import os
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.models import (
    TextSendMessage,
)
from pymongo import MongoClient
import redis
import abc

from CommandException import CommandException


class AbstractLineMessageHandler(abc.ABC):
    HELP_MESSAGE = str

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

    def handle_event(self, event):
        sender_id = event.source.sender_id
        message = event.message.text
        commands = message.split(' ')

        reply_token = event.reply_token
        if reply_token != '00000000000000000000000000000000':
            try:
                messages = self._map_action(commands)(sender_id=sender_id, commands=commands)

                if isinstance(messages, str):
                    self.reply_message(reply_token, messages)
                elif isinstance(messages, list):
                    for message in messages:
                        self.push_message(sender_id, message)
            except CommandException as e:
                self.reply_message(reply_token, str(e))
            except Exception as e:
                self.reply_message(reply_token, '系統異常')
                # self.reply_message(reply_token, str(e))

    @abc.abstractmethod
    def _map_action(self, commands):
        return NotImplemented

    @staticmethod
    @abc.abstractmethod
    def help_message():
        return NotImplemented

    def push_message(self, to, message_text):
        self.line_bot_api.push_message(
            to,
            TextSendMessage(text=message_text))

    def reply_message(self, reply_token, message_text):
        self.line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=message_text))
